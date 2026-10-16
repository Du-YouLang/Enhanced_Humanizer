"""Auditable legacy presentation aliases; never change candidate files or arrays.

Only two underdefined no-NF auxiliary scalars and synonymous ROI keys may have
alternate representations. All other fields remain with the frozen owner judge.
"""
import copy
import math

REVISION='AF_STROKE_LEGACY_REPRESENTATION_20261016_V4'
ROI_KEYS=('roi','roi_motor','roi_order')
NF='natural_frequency_motor_hz'
MAX='natural_frequency_motor_max_profile_db'
BOUNDARY='natural_frequency_motor_at_grid_boundary'


def canonical_views(actual,reference):
    a=copy.deepcopy(actual);r=copy.deepcopy(reference);changes=[]
    metadata=a.get('metadata',{})
    present=[k for k in ROI_KEYS if k in metadata]
    if not present:raise ValueError('A current ordered ROI field is required')
    ordered={}
    for key in present:
        value=metadata[key]
        if isinstance(value,dict):
            if key!='roi_order' or set(value)!={'motor'}:
                raise ValueError('Only an explicit motor ROI order object is supported')
            value=value['motor']
        ordered[key]=value
    if any(ordered[k]!=ordered[present[0]] for k in present):raise ValueError('Conflicting ROI representations')
    if not isinstance(ordered[present[0]],list) or not all(isinstance(v,str) for v in ordered[present[0]]):
        raise ValueError('Ordered ROI names must be strings')
    if ordered[present[0]]!=r['metadata']['roi']:raise ValueError('ROI order differs from frozen reference')
    if 'roi' not in metadata:
        metadata['roi']=copy.deepcopy(ordered[present[0]])
        changes.append({'field':'metadata.roi','source_alias':present[0]})
    for key in ('artifact_reviewed','synthetic','pci_available','allow_unreviewed'):
        if type(metadata.get(key)) is not bool:raise ValueError('Original boolean metadata type required: '+key)
    scalars=a.get('scalars',{});gold=r['scalars']
    if NF not in scalars or MAX not in scalars or BOUNDARY not in scalars:
        raise ValueError('Required natural-frequency scalar keys are missing')
    # The frozen reference still decides whether any natural frequency exists.
    # Neither a spurious NF nor a missing detected NF can use this compatibility.
    if gold[NF] is None and scalars[NF] is None:
        value=scalars[MAX];expected=gold[MAX]
        if value is not None:
            if (type(value) not in (int,float) or not math.isfinite(value)
                    or type(expected) not in (int,float) or not math.isfinite(expected)
                    or abs(value-expected)>1e-4+1e-5*abs(expected)):
                raise ValueError('Provided no-NF profile maximum is numerically wrong')
        flag=scalars[BOUNDARY]
        if flag is not None and (type(flag) is not bool or flag is not False):
            raise ValueError('A non-existent NF cannot be flagged as a boundary peak')
        # Undefined auxiliary presentation is canonical null for both views;
        # do not inject any reference numeric value into a candidate result.
        for key in (MAX,BOUNDARY):
            changes.append({'field':'scalars.'+key,'actual_original':scalars[key],'reference_original':gold[key],
                            'canonical':None,'condition':'NF_NOT_DETECTED'})
            scalars[key]=None;gold[key]=None
    return a,r,changes
