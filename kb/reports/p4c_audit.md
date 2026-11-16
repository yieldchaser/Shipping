# P4c random audit

- judge: `glm-5.3` (glm family) vs extractor `DeepSeek-V4.1-Flash` (deepseek family) — different family: yes
- sample: 200 records of 183486 available (seed 196579347)
- judged: 200, keep 199, drop 1, unparseable 0 -> **wrong 1 (0.50%)**, gate 3%

| audit id | chunk | kind | verdict | reason |
|---|---|---|---|---|
| a000 | `6f182433589e8dbd766479494e36663b` | state_facts | keep | number 11 in quote; new entity verified; no direction field |
| a001 | `255b68751e1d5d1b01395b261910e773` | events | keep | All printed numbers appear in quote; references resolve |
| a002 | `a955f5dcbd8e249f92c60217b3121d0f` | claims | keep | no printed numbers; new id verified; direction legal |
| a003 | `ff6beadd3c28fe902926d2e65f784c65` | claims | keep | no number tokens, country:BD resolves, direction legal |
| a004 | `50359fdb58e34c53daf4af05d477cf58` | events | keep | no number tokens, country:IN resolves, no direction field |
| a005 | `0390dbe3b3ea178a43397bd814cbc21f` | events | keep | number 14 present in quote; no refs; no direction |
| a006 | `5bafa4a77e327873c8a9ad8d938ab6cd` | claims | keep | no printed numbers, no entity refs, direction legal |
| a007 | `e2e47d66ba8558d7c59ffb5948b9849b` | events | keep | number 15 appears in quote; no entity references; no direction |
| a008 | `c1dac0a90ad3523580329e3a79767b39` | events | keep | number 2q12 present in quote; route:TC5 is existing id |
| a009 | `7a02efb25c1b8d0379331ffe07a1f561` | claims | keep | no number tokens; new id verified; direction legal |
| a010 | `06dee69d07a489b31d5a1bacd21ddac3` | events | keep | no printed numbers; all references resolve; no direction field |
| a011 | `e2a0023ad18626b80b37d2c21c328366` | state_facts | keep | all number tokens present, new ids verified |
| a012 | `261d8ae715fb2cd49fe2ccf0710e48e6` | events | keep | all printed numbers (55, 40s) appear in quote; no refs or direction |
| a013 | `4df9c6e8d9f2f09a4f00f1520a7b7c9e` | claims | keep | no printed numbers, references resolve, direction legal |
| a014 | `f0cc1f3e2b63cf0358704c6598543841` | claims | keep | All rules pass: 2026 in quote, existing ids resolve, direction legal |
| a015 | `8caa23a7c94230aa709a9cae3bff6f90` | events | keep | numbers 3-6 in quote; existing ids resolve; no direction field |
| a016 | `eaaefb43ca67e4e96092327ab4c85f20` | events | keep | no number tokens, no entity references, no direction field |
| a017 | `2bc13c92271be29825814b9f6c7bf397` | events | keep | number 30,000 in quote; commodity id is existing form |
| a018 | `d63f861f0b688bcef4c75259fc6898d6` | claims | keep | No number tokens, no entity references, direction 'up' is legal |
| a019 | `9c86b27fc61fa6fa07b0fdad742982fb` | claims | keep | no number tokens, no entity refs, direction legal |
| a020 | `c88a64c3ba3a76ce2789b8cb2d93307e` | events | keep | all printed numbers appear in quote; no references; no direction |
| a021 | `2b36e6b0da497f7e71bc8a29f6dd1610` | events | keep | W115 appears in quote; new entities verified; no direction field |
| a022 | `052261d9b4783be161ba58e8e076127b` | events | keep | no digit tokens in printed fields; country:RU resolves as existing id |
| a023 | `465aa46a7e2d4f402657c8f07a4a8ca2` | claims | keep | no printed numbers, existing id resolves, direction legal |
| a024 | `96b435d3a6f426d9d9843371ce70ee9c` | events | keep | no printed numbers; all references resolve under rule 4 |
| a025 | `fcdd75fed8a6bafd98a01c9fe4f5fbe9` | events | keep | no number tokens; new:brazil verified; no direction field |
| a026 | `d48c0d7cb403dc3cc75139b442f00a7e` | claims | keep | No number tokens, no entity refs, direction is legal |
| a027 | `a6cd6e787fe393a239d8d3bed3531307` | claims | keep | no number tokens; subject resolves via new_entities_verified; directio |
| a028 | `797adaa605b7d1888ab57545c478aa5b` | events | keep | numbers 1 and 2013 in quote; entity id resolves per rule 4 |
| a029 | `c88d3256d8afa92289827f8a96ab8c3c` | claims | keep | no printed numbers, no entity refs, direction is legal |
| a030 | `598b1d427fadbd7cae7f9fab43e19d55` | events | keep | all printed numbers in quote; entity id resolves |
| a031 | `4599ee14a86e7315794a7d9c4a3568b2` | claims | keep | no printed numbers, references resolve, direction legal |
| a032 | `e12661557e7f8a075351d0b9577f4825` | events | keep | all printed numbers appear in quote; no refs or direction |
| a033 | `e4c088724784587e75203e9c1a5bc653` | claims | keep | No printed numbers, references resolve, direction is legal |
| a034 | `80e810d0ebbc4434d06666e789d53abe` | claims | keep | no printed numbers, no references, direction 'na' is legal |
| a035 | `fb6e47df012b7545a559a8dc20160ff5` | events | keep | number $1.25 in quote; route:BLPG2 existing id resolves |
| a036 | `02d17017b3d63c6da7f53b260d8e7d1a` | claims | keep | All checks pass: number 2022 in quote, references resolve, direction l |
| a037 | `7b0ce6946340550a50f8460d4fb696e2` | events | keep | all printed numbers present in quote; no references to check |
| a038 | `e5b4a9fb75dfdbcb528ad6f556f6f247` | claims | keep | no number tokens, no entity refs, direction na is legal |
| a039 | `d217407de3bf1e86876d0a1a46a6527b` | state_facts | keep | numbers present in quote; references resolve; no direction field |
