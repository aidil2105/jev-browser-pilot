| chooser | correct | accuracy | answered | median ms | range ms | in tok | cost |
|---|---|---|---|---|---|---|---|
| jev | 25/27 | 93% | 27/27 | 316 | 278-1141 | 167398 | $0.007031 |
| openai:cl/cline-free/muse-spark-1.3-contributor | 1/27 | 4% | 1/27 | 10 | 4-3073 | 3457 | $0.000000 |

| case | chooser | expect | got | correct | conf | ms |
|---|---|---|---|---|---|---|
| calculator->slide_rule | jev | id:100 | a 'slide rule' | yes | 0.91 | 1141 |
| calculator->slide_rule | openai:cl/cline-free/muse-spark-1.3-contributor | id:100 | a 'slide rule' | yes |  | 1362 |
| calculator->already-open | jev | __done__ | done | yes | 0.99 | 281 |
| calculator->already-open | openai:cl/cline-free/muse-spark-1.3-contributor | __done__ | error | no |  | 3073 |
| calculator->unreachable | jev | __stuck__ | stuck | yes | 0.99 | 330 |
| calculator->unreachable | openai:cl/cline-free/muse-spark-1.3-contributor | __stuck__ | error | no |  | 4 |
| slide_rule->william_oughtred | jev | id:14 | a 'William Oughtred' | yes | 0.99 | 409 |
| slide_rule->william_oughtred | openai:cl/cline-free/muse-spark-1.3-contributor | id:14 | error | no |  | 5 |
| slide_rule->already-open | jev | __done__ | done | yes | 0.99 | 312 |
| slide_rule->already-open | openai:cl/cline-free/muse-spark-1.3-contributor | __done__ | error | no |  | 8 |
| slide_rule->unreachable | jev | __stuck__ | stuck | yes | 0.96 | 291 |
| slide_rule->unreachable | openai:cl/cline-free/muse-spark-1.3-contributor | __stuck__ | error | no |  | 5 |
| william_oughtred->richard_delamaine | jev | id:88 | a 'Richard Delamain' | no | 0.50 | 334 |
| william_oughtred->richard_delamaine | openai:cl/cline-free/muse-spark-1.3-contributor | id:88 | error | no |  | 5 |
| william_oughtred->already-open | jev | __done__ | done | yes | 0.99 | 348 |
| william_oughtred->already-open | openai:cl/cline-free/muse-spark-1.3-contributor | __done__ | error | no |  | 5 |
| william_oughtred->unreachable | jev | __stuck__ | stuck | yes | 0.95 | 316 |
| william_oughtred->unreachable | openai:cl/cline-free/muse-spark-1.3-contributor | __stuck__ | error | no |  | 4 |
| logarithm->john_napier | jev | id:15 | a 'John Napier' | yes | 0.99 | 645 |
| logarithm->john_napier | openai:cl/cline-free/muse-spark-1.3-contributor | id:15 | error | no |  | 14 |
| logarithm->slide_rule | jev | id:21 | a 'slide rule' | yes | 0.98 | 307 |
| logarithm->slide_rule | openai:cl/cline-free/muse-spark-1.3-contributor | id:21 | error | no |  | 15 |
| logarithm->already-open | jev | __done__ | done | yes | 0.99 | 341 |
| logarithm->already-open | openai:cl/cline-free/muse-spark-1.3-contributor | __done__ | error | no |  | 15 |
| logarithm->unreachable | jev | __stuck__ | stuck | yes | 0.95 | 317 |
| logarithm->unreachable | openai:cl/cline-free/muse-spark-1.3-contributor | __stuck__ | error | no |  | 5 |
| abacus->slide_rule | jev | id:148 | a 'Slide rule' | yes | 0.97 | 327 |
| abacus->slide_rule | openai:cl/cline-free/muse-spark-1.3-contributor | id:148 | error | no |  | 4 |
| abacus->roman_abacus | jev | id:15 | a 'Roman abacus' | yes | 0.99 | 287 |
| abacus->roman_abacus | openai:cl/cline-free/muse-spark-1.3-contributor | id:15 | error | no |  | 14 |
| abacus->already-open | jev | __done__ | done | yes | 0.99 | 315 |
| abacus->already-open | openai:cl/cline-free/muse-spark-1.3-contributor | __done__ | error | no |  | 10 |
| abacus->unreachable | jev | __stuck__ | stuck | yes | 0.98 | 299 |
| abacus->unreachable | openai:cl/cline-free/muse-spark-1.3-contributor | __stuck__ | error | no |  | 20 |
| mechanical_calculator->slide_rule | jev | id:4 | a 'slide rule' | yes | 0.97 | 338 |
| mechanical_calculator->slide_rule | openai:cl/cline-free/muse-spark-1.3-contributor | id:4 | error | no |  | 14 |
| mechanical_calculator->difference_engine | jev | id:20 | a 'difference engine' | yes | 0.98 | 312 |
| mechanical_calculator->difference_engine | openai:cl/cline-free/muse-spark-1.3-contributor | id:20 | error | no |  | 14 |
| mechanical_calculator->already-open | jev | __done__ | done | yes | 0.99 | 312 |
| mechanical_calculator->already-open | openai:cl/cline-free/muse-spark-1.3-contributor | __done__ | error | no |  | 13 |
| mechanical_calculator->unreachable | jev | __stuck__ | stuck | yes | 0.99 | 386 |
| mechanical_calculator->unreachable | openai:cl/cline-free/muse-spark-1.3-contributor | __stuck__ | error | no |  | 14 |
| nomogram->slide_rule | jev | id:7 | a 'slide rule' | yes | 0.83 | 315 |
| nomogram->slide_rule | openai:cl/cline-free/muse-spark-1.3-contributor | id:7 | error | no |  | 14 |
| nomogram->already-open | jev | __done__ | done | yes | 0.99 | 321 |
| nomogram->already-open | openai:cl/cline-free/muse-spark-1.3-contributor | __done__ | error | no |  | 4 |
| nomogram->unreachable | jev | __stuck__ | stuck | yes | 0.98 | 278 |
| nomogram->unreachable | openai:cl/cline-free/muse-spark-1.3-contributor | __stuck__ | error | no |  | 15 |
| richter_scale->logarithm | jev | id:5 | stuck | no | 0.35 | 341 |
| richter_scale->logarithm | openai:cl/cline-free/muse-spark-1.3-contributor | id:5 | error | no |  | 6 |
| richter_scale->already-open | jev | __done__ | done | yes | 0.97 | 305 |
| richter_scale->already-open | openai:cl/cline-free/muse-spark-1.3-contributor | __done__ | error | no |  | 4 |
| richter_scale->unreachable | jev | __stuck__ | stuck | yes | 0.97 | 302 |
| richter_scale->unreachable | openai:cl/cline-free/muse-spark-1.3-contributor | __stuck__ | error | no |  | 4 |
