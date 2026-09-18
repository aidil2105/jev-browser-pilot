| chooser | correct | accuracy | answered | median ms | range ms | in tok | cost |
|---|---|---|---|---|---|---|---|
| openai:qwen/qwen3-30b-a3b-instruct-2507 | 10/27 | 37% | 27/27 | 1339 | 515-3448 | 113085 | $0.000000 |
| openai:meta-llama/llama-3.1-8b-instruct | 9/27 | 33% | 27/27 | 1146 | 552-3854 | 96930 | $0.000000 |

| case | chooser | expect | got | correct | conf | ms |
|---|---|---|---|---|---|---|
| calculator->slide_rule | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:100 | a 'slide rule' | yes |  | 1754 |
| calculator->slide_rule | openai:meta-llama/llama-3.1-8b-instruct | id:100 | a 'slide rule' | yes |  | 3437 |
| calculator->already-open | openai:qwen/qwen3-30b-a3b-instruct-2507 | __done__ | a 'seven-segment' | no |  | 1114 |
| calculator->already-open | openai:meta-llama/llama-3.1-8b-instruct | __done__ | a 'electronic' | no |  | 894 |
| calculator->unreachable | openai:qwen/qwen3-30b-a3b-instruct-2507 | __stuck__ | done | no |  | 1308 |
| calculator->unreachable | openai:meta-llama/llama-3.1-8b-instruct | __stuck__ | a 'Renaissance' | no |  | 1025 |
| slide_rule->william_oughtred | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:14 | a 'William Oughtred' | yes |  | 2867 |
| slide_rule->william_oughtred | openai:meta-llama/llama-3.1-8b-instruct | id:14 | a 'William Oughtred' | yes |  | 1309 |
| slide_rule->already-open | openai:qwen/qwen3-30b-a3b-instruct-2507 | __done__ | a 'Slide Rule' | no |  | 537 |
| slide_rule->already-open | openai:meta-llama/llama-3.1-8b-instruct | __done__ | a 'logarithms' | no |  | 775 |
| slide_rule->unreachable | openai:qwen/qwen3-30b-a3b-instruct-2507 | __stuck__ | done | no |  | 1098 |
| slide_rule->unreachable | openai:meta-llama/llama-3.1-8b-instruct | __stuck__ | a '"Slide Rules"' | no |  | 770 |
| william_oughtred->richard_delamaine | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:88 | a 'Richard Delamain' | no |  | 3448 |
| william_oughtred->richard_delamaine | openai:meta-llama/llama-3.1-8b-instruct | id:88 | a 'Richard Delamain' | no |  | 1172 |
| william_oughtred->already-open | openai:qwen/qwen3-30b-a3b-instruct-2507 | __done__ | a 'AWT-urd' | no |  | 974 |
| william_oughtred->already-open | openai:meta-llama/llama-3.1-8b-instruct | __done__ | a 'Anglican clergyman' | no |  | 1072 |
| william_oughtred->unreachable | openai:qwen/qwen3-30b-a3b-instruct-2507 | __stuck__ | a 'Google' | no |  | 749 |
| william_oughtred->unreachable | openai:meta-llama/llama-3.1-8b-instruct | __stuck__ | a '"Oughtred, William"' | no |  | 1235 |
| logarithm->john_napier | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:15 | a 'John Napier' | yes |  | 2431 |
| logarithm->john_napier | openai:meta-llama/llama-3.1-8b-instruct | id:15 | a 'John Napier' | yes |  | 1184 |
| logarithm->slide_rule | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:21 | a 'slide rule' | yes |  | 674 |
| logarithm->slide_rule | openai:meta-llama/llama-3.1-8b-instruct | id:21 | a 'slide rule' | yes |  | 721 |
| logarithm->already-open | openai:qwen/qwen3-30b-a3b-instruct-2507 | __done__ | a 'mathematics' | no |  | 1339 |
| logarithm->already-open | openai:meta-llama/llama-3.1-8b-instruct | __done__ | a 'mathematics' | no |  | 1387 |
| logarithm->unreachable | openai:qwen/qwen3-30b-a3b-instruct-2507 | __stuck__ | a 'mathematics' | no |  | 959 |
| logarithm->unreachable | openai:meta-llama/llama-3.1-8b-instruct | __stuck__ | a 'common logarithm' | no |  | 1881 |
| abacus->slide_rule | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:148 | a 'Slide rule' | yes |  | 2397 |
| abacus->slide_rule | openai:meta-llama/llama-3.1-8b-instruct | id:148 | a 'Slide rule' | yes |  | 1132 |
| abacus->roman_abacus | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:15 | a 'Roman abacus' | yes |  | 1139 |
| abacus->roman_abacus | openai:meta-llama/llama-3.1-8b-instruct | id:15 | a 'Roman abacus' | yes |  | 1090 |
| abacus->already-open | openai:qwen/qwen3-30b-a3b-instruct-2507 | __done__ | a 'Abacus' | no |  | 527 |
| abacus->already-open | openai:meta-llama/llama-3.1-8b-instruct | __done__ | a 'Abacus' | no |  | 1151 |
| abacus->unreachable | openai:qwen/qwen3-30b-a3b-instruct-2507 | __stuck__ | a 'Abacus' | no |  | 2246 |
| abacus->unreachable | openai:meta-llama/llama-3.1-8b-instruct | __stuck__ | a 'Abacus' | no |  | 552 |
| mechanical_calculator->slide_rule | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:4 | a 'slide rule' | yes |  | 2586 |
| mechanical_calculator->slide_rule | openai:meta-llama/llama-3.1-8b-instruct | id:4 | a 'slide rule' | yes |  | 1338 |
| mechanical_calculator->difference_engine | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:20 | a 'difference engine' | yes |  | 1179 |
| mechanical_calculator->difference_engine | openai:meta-llama/llama-3.1-8b-instruct | id:20 | a 'difference engine' | yes |  | 599 |
| mechanical_calculator->already-open | openai:qwen/qwen3-30b-a3b-instruct-2507 | __done__ | a 'Arithmometer' | no |  | 1773 |
| mechanical_calculator->already-open | openai:meta-llama/llama-3.1-8b-instruct | __done__ | a 'Tabulating machine' | no |  | 745 |
| mechanical_calculator->unreachable | openai:qwen/qwen3-30b-a3b-instruct-2507 | __stuck__ | a 'Arithmometer' | no |  | 2483 |
| mechanical_calculator->unreachable | openai:meta-llama/llama-3.1-8b-instruct | __stuck__ | a 'Arithmometer' | no |  | 1562 |
| nomogram->slide_rule | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:7 | a 'slide rule' | yes |  | 2291 |
| nomogram->slide_rule | openai:meta-llama/llama-3.1-8b-instruct | id:7 | a 'slide rule' | yes |  | 1478 |
| nomogram->already-open | openai:qwen/qwen3-30b-a3b-instruct-2507 | __done__ | a 'nomogram' | no |  | 643 |
| nomogram->already-open | openai:meta-llama/llama-3.1-8b-instruct | __done__ | a 'nomogram' | no |  | 1146 |
| nomogram->unreachable | openai:qwen/qwen3-30b-a3b-instruct-2507 | __stuck__ | a 'nomogram' | no |  | 2086 |
| nomogram->unreachable | openai:meta-llama/llama-3.1-8b-instruct | __stuck__ | a 'slide rule' | no |  | 1772 |
| richter_scale->logarithm | openai:qwen/qwen3-30b-a3b-instruct-2507 | id:5 | a 'logarithmic' | yes |  | 1560 |
| richter_scale->logarithm | openai:meta-llama/llama-3.1-8b-instruct | id:5 | a 'common logarithms' | no |  | 704 |
| richter_scale->already-open | openai:qwen/qwen3-30b-a3b-instruct-2507 | __done__ | a 'https://en.wikipedia.org/w/index.php?title=Richter_scale&oldid=1375021' | no |  | 3312 |
| richter_scale->already-open | openai:meta-llama/llama-3.1-8b-instruct | __done__ | a '"Richter scale"' | no |  | 3854 |
| richter_scale->unreachable | openai:qwen/qwen3-30b-a3b-instruct-2507 | __stuck__ | a 'https://en.wikipedia.org/w/index.php?title=Richter_scale&oldid=1375021' | no |  | 515 |
| richter_scale->unreachable | openai:meta-llama/llama-3.1-8b-instruct | __stuck__ | a 'the original' | no |  | 750 |
