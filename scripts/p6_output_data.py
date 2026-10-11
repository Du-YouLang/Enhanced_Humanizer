"""Bound candidate numeric output before a trusted parent allocates any arrays."""
import ast
import io
import json
from pathlib import Path
import struct
import zipfile


def bounded_npy(path, *, max_bytes=128_000_000, max_elements=16_000_000):
    import numpy as np
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>max_bytes:
        raise ValueError('NPY output exceeds the frozen data boundary')
    with path.open('rb') as file:
        version=np.lib.format.read_magic(file)
        if version not in ((1,0),(2,0)):raise ValueError('Unsupported numeric NPY version')
        reader=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
        shape,_,dtype=reader(file,max_header_size=8192)
        if dtype.hasobject or dtype.fields or dtype.kind not in 'biufc' or dtype.itemsize>16:
            raise ValueError('Only plain numeric arrays are permitted')
        count=1
        if len(shape)>8:raise ValueError('Array dimension count exceeded')
        for size in shape:
            if type(size) is not int or not 0<=size<=max_elements:raise ValueError('Invalid array dimension')
            count*=size
            if count>max_elements:raise ValueError('Array element limit exceeded')
        if file.tell()+count*dtype.itemsize!=path.stat().st_size:raise ValueError('NPY size/shape mismatch')
    return np.load(path,allow_pickle=False,max_header_size=8192)


def bounded_json(path, *, max_bytes=2_000_000):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > max_bytes:
        raise ValueError('JSON output exceeds the frozen data boundary')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def constant(value): raise ValueError('Nonstandard JSON numeric constant')
    return json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=constant)


def bounded_npz(path, *, max_bytes=128_000_000, max_arrays=128,
                max_elements=16_000_000, expected_keys=None):
    """Check ZIP and NPY headers before calling NumPy; never permit object pickle.

    The controller reads only regular files after the candidate PID namespace has
    exited. Limits apply to decompressed sizes and declared array shapes too.
    """
    import numpy as np
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError('NPZ output exceeds the frozen data boundary')
    specifications = {}
    total = 0
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > max_arrays: raise ValueError('Too many output arrays')
        for entry in entries:
            name = entry.filename
            if (not name.endswith('.npy') or '/' in name or '\\' in name
                    or name[:-4] in specifications or entry.flag_bits & 1
                    or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError('Unsafe or duplicate NPZ member')
            total += entry.file_size
            if entry.file_size > max_bytes or total > max_bytes:
                raise ValueError('Decompressed NPZ output exceeds the frozen limit')
            with archive.open(entry) as member:
                if member.read(6) != b'\x93NUMPY': raise ValueError('Invalid NPY magic')
                version = member.read(2)
                width = 2 if version == b'\x01\x00' else 4
                if version not in (b'\x01\x00', b'\x02\x00', b'\x03\x00'):
                    raise ValueError('Unsupported NPY version')
                length_raw = member.read(width)
                if len(length_raw) != width: raise ValueError('Truncated NPY header')
                length = struct.unpack('<H' if width == 2 else '<I', length_raw)[0]
                if length > 8192: raise ValueError('Oversized NPY header')
                header = member.read(length)
                if len(header) != length: raise ValueError('Truncated NPY header')
                info = ast.literal_eval(header.decode('utf-8' if version == b'\x03\x00' else 'latin1'))
                if type(info) is not dict or set(info) != {'descr','fortran_order','shape'}:
                    raise ValueError('Invalid NPY header schema')
                dtype = np.dtype(info['descr']); shape = info['shape']
                if dtype.hasobject or dtype.fields or dtype.kind not in 'biufc':
                    raise ValueError('Only plain numeric and boolean arrays are permitted')
                if type(shape) is not tuple or len(shape) > 8 or type(info['fortran_order']) is not bool:
                    raise ValueError('Invalid array shape/order')
                count = 1
                for dimension in shape:
                    if type(dimension) is not int or not 0 <= dimension <= max_elements:
                        raise ValueError('Invalid array dimension')
                    count *= dimension
                    if count > max_elements: raise ValueError('Array element limit exceeded')
                if dtype.itemsize > 16 or 8+width+length+count*dtype.itemsize != entry.file_size:
                    raise ValueError('NPY byte size differs from declared shape')
                specifications[name[:-4]] = (shape, dtype)
        if expected_keys is not None and set(specifications) != set(expected_keys):
            raise ValueError('Output array names differ from the contract')
        # CRC and decompression errors propagate. No candidate modules are imported.
        arrays = {}
        for name, (shape, dtype) in specifications.items():
            raw = archive.read(name+'.npy')
            array = np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=8192)
            if array.shape != shape or array.dtype != dtype: raise ValueError('Array schema changed')
            arrays[name] = array
        return arrays
