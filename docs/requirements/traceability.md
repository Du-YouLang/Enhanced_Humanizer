# PRD v0.4 需求追踪

完整保留 86 个稳定 ID：80 项主需求和 6 项操作待决项。原始来源 S0–S4 及附录 A–C 保存在原文；[C]/[E]/[P]/[F]/[O] 不相互替代。

机器可筛选数据见 [traceability.json](traceability.json)，phase_evidence 保存已执行证据。测试计划不能视为已通过；阶段验收不等于整个需求已经实现。

| ID | 标签 | 来源 | Phase | Issue 草案 | Tests（计划） | 实施状态 | ADR |
|---|---|---|---|---|---|---|---|
| V-01 | C | S1/S2 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| V-02 | C | S1/S2 | P1/P3 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04; P3-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| V-03 | C | S2 | P5 | [P5](../issues/P5.md) 待建远程 | P5-A01..A03 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| V-04 | E | S1–S4 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| V-05 | C | S2 | P0/P1 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P1-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md), [ADR-0006](../decisions/ADR-0006.md) |
| WF-01 | C | S1/S2 | P0/P1 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P1-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md), [ADR-0006](../decisions/ADR-0006.md) |
| WF-02 | C | S2/S3 | P1 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| WF-03 | C | S3 | P1/P3 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04; P3-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| WF-04 | P/E | S0 | P1 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| WF-05 | C | S2/S3 | P3 | [P3](../issues/P3.md) 待建远程 | P3-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| WF-06 | P | S0/S3 | P1/P4 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04; P4-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| WF-07 | C/P | S1/S3 | P1/P4 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04; P4-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| WF-08 | F | S2 | FUTURE | 后续立项 | 后续立项 | DEFERRED_FUTURE | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-01 | C | S2/S3 | P2 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-02 | C | S3 | P2 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-03 | C | S3 | P2 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-04 | C | S3 | P2 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-05 | E | S0/S1 | P2/P6 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-06 | P/E | S0/S2 | P2/P6 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-07 | C | S3 | P2/P3 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P3-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-08 | C | S3 | P2/P3 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P3-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-09 | E | S1/S3 | P1/P6 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04; P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| DS-10 | P | S0 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| JR-01 | C | S2–S4 | P0/P2/P6 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P2-A01..A04; P6-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md), [ADR-0006](../decisions/ADR-0006.md) |
| JR-02 | C | S3/S4 | P0/P2/P6 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P2-A01..A04; P6-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md), [ADR-0006](../decisions/ADR-0006.md) |
| JR-03 | C | S3 | P0/P2 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P2-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md), [ADR-0006](../decisions/ADR-0006.md) |
| JR-04 | C | S3/S4 | P3 | [P3](../issues/P3.md) 待建远程 | P3-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| JR-05 | C | S3/S4 | P3 | [P3](../issues/P3.md) 待建远程 | P3-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| JR-06 | C | S3 | P3 | [P3](../issues/P3.md) 待建远程 | P3-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| JR-07 | E | S3/S4 | P3/P6 | [P3](../issues/P3.md) 待建远程 | P3-A01..A04; P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| JR-08 | P | S1/S3 | P2/P3 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P3-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| JR-09 | F/P | S0 | FUTURE | 后续立项 | 后续立项 | DEFERRED_FUTURE | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| HR-01 | C | S2 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | P0_ACCEPTANCE_READY_PENDING_CURRENT_CI | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| HR-02 | C | S2/S3 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | P0_ACCEPTANCE_READY_PENDING_CURRENT_CI | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| HR-03 | C | S4 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | P0_ACCEPTANCE_READY_PENDING_CURRENT_CI | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| HR-04 | F | S3 | FUTURE | 后续立项 | 后续立项 | DEFERRED_FUTURE | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| HR-05 | C | S3/S4 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| HR-06 | F | S3/S4 | FUTURE | 后续立项 | 后续立项 | DEFERRED_FUTURE | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| HR-07 | C/P | S3 | P0/P2 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P2-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| CX-01 | C | S2/S3 | P4 | [P4](../issues/P4.md) 待建远程 | P4-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| CX-02 | C | S3 | P4 | [P4](../issues/P4.md) 待建远程 | P4-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| CX-03 | C/P | S3 | P4 | [P4](../issues/P4.md) 待建远程 | P4-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| CX-04 | C | S3 | P4 | [P4](../issues/P4.md) 待建远程 | P4-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| CX-05 | P | S0/S3 | P4 | [P4](../issues/P4.md) 待建远程 | P4-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| CX-06 | P/E | S3 | P4/P6 | [P4](../issues/P4.md) 待建远程 | P4-A01..A04; P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| GC-01 | C | S3 | P0/P4 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P4-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| GC-02 | C | S3 | P0/P4 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P4-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| GC-03 | C | S3 | P2/P4 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P4-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| GC-04 | C | S3 | P0/P4 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P4-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| GC-05 | C | S3 | P0/P4 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P4-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| GC-06 | C | S3 | P0/P4 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P4-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| GC-07 | C/P | S3 | P0/P4 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P4-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| UI-01 | C | S2/S3 | P5 | [P5](../issues/P5.md) 待建远程 | P5-A01..A03 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| UI-02 | C | S2/S3 | P5 | [P5](../issues/P5.md) 待建远程 | P5-A01..A03 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| UI-03 | C | S3 | P5 | [P5](../issues/P5.md) 待建远程 | P5-A01..A03 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| UI-04 | C | S3 | P5 | [P5](../issues/P5.md) 待建远程 | P5-A01..A03 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| UI-05 | P | S2/S3 | P5 | [P5](../issues/P5.md) 待建远程 | P5-A01..A03 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| UI-06 | C/P | S3 | P5 | [P5](../issues/P5.md) 待建远程 | P5-A01..A03 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-01 | C | S2–S4 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-02 | C | S3 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-03 | C | S4 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-04 | C | S3 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-05 | C | S4 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-06 | C | S2/S3 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-07 | C | S3 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-08 | C | S3 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-09 | C | S3 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-10 | O | S3/S4 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PENDING_USER_DECISION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-11 | E | S0 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| BM-12 | F | S4 | FUTURE | 后续立项 | 后续立项 | DEFERRED_FUTURE | [ADR-0001](../decisions/ADR-0001.md), [ADR-0002](../decisions/ADR-0002.md) |
| OP-01 | C | S1/S3 | P2/P6 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| OP-02 | P | S0 | P2/P6 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| OP-03 | C/E | S1 | P1/P6 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04; P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| OP-04 | P | S0/S3 | P2/P6 | [P2](../issues/P2.md) 待建远程 | P2-A01..A04; P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| OP-05 | F | S0 | FUTURE | 后续立项 | 后续立项 | DEFERRED_FUTURE | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| SG-01 | C | S3 | P0/P2 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08; P2-A01..A04 | P0_AUDIT_PASSED_LATER_PHASES_PENDING | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| SG-02 | C | S3 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | P0_ACCEPTANCE_READY_PENDING_CURRENT_CI | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| SG-03 | C | S3 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | P0_ACCEPTANCE_READY_PENDING_CURRENT_CI | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| SG-04 | C | S1/S3 | P4/P6 | [P4](../issues/P4.md) 待建远程 | P4-A01..A04; P6-A01..A04 | PLANNED | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| SG-05 | P | S1/S3 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PLANNED_STUDY_OR_OPTION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| O-01 | O | PRD §13 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | USER_DECISION_RECORDED_P0 | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| O-02 | O | PRD §13 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | USER_DECISION_RECORDED_P0 | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| O-03 | O | PRD §13 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | USER_DECISION_RECORDED_P0 | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| O-04 | O | PRD §13 | P0 | [P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1) | P0-A01..A08 | USER_DECISION_RECORDED_P0 | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md), [ADR-0006](../decisions/ADR-0006.md) |
| O-05 | O | PRD §13 | P6 | [P6](../issues/P6.md) 待建远程 | P6-A01..A04 | PENDING_USER_DECISION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |
| O-06 | O | PRD §13 | P1/P5 | [P1](../issues/P1.md) 待建远程 | P1-A01..A04; P5-A01..A03 | PENDING_USER_DECISION | [ADR-0001](../decisions/ADR-0001.md), [ADR-0003](../decisions/ADR-0003.md) |

USR-NAME-01：已记录用户最新命名要求，见 [项目状态](../project-status.md)。此项是新增用户指示，未擅自改写 PRD 的稳定 ID。
