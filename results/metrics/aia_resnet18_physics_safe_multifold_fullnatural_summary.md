# AIA ResNet18 Physics-Safe Multi-Fold Full-Natural Summary

## Fold-level official test metrics

| fold_id   | source_file                                                                                                    |   train_rows |   val_rows |   test_rows |   test_positives |   test_negatives |   best_epoch |   threshold |   roc_auc |   pr_auc |   brier_score |   accuracy |   precision |   recall |   specificity |     f1 |    tss |    hss |   tp |   tn |   fp |   fn |   diagnostic_test_best_tss |
|:----------|:---------------------------------------------------------------------------------------------------------------|-------------:|-----------:|------------:|-----------------:|-----------------:|-------------:|------------:|----------:|---------:|--------------:|-----------:|------------:|---------:|--------------:|-------:|-------:|-------:|-----:|-----:|-----:|-----:|---------------------------:|
| test_2013 | results/metrics/aia_resnet18_physics_safe_multifold_fullnatural_test_2013_metrics.json                         |        14448 |      10815 |       13066 |              492 |            12574 |            1 |      0.05   |    0.6592 |   0.0563 |         0.095 |     0.5113 |      0.0548 |   0.7378 |        0.5024 | 0.1021 | 0.2402 | 0.0344 |  363 | 6317 | 6257 |  129 |                     0.2538 |
| test_2014 | results/metrics/aia_resnet18_physics_safe_multifold_fullnatural_test_2014_metrics.json                         |        25263 |      13066 |       11627 |              629 |            10998 |            3 |      0.0075 |    0.4975 |   0.0541 |         0.082 |     0.6105 |      0.0552 |   0.3847 |        0.6234 | 0.0965 | 0.0081 | 0.0021 |  242 | 6856 | 4142 |  387 |                     0.0092 |
| test_2015 | results/metrics/aia_resnet18_physics_safe_fold2015_fullnatural_benchmark_fullnatural_physics_safe_metrics.json |        38329 |      11627 |       11236 |              531 |            10705 |            1 |      0.205  |    0.7477 |   0.0971 |         0.199 |     0.5986 |      0.0941 |   0.8682 |        0.5852 | 0.1697 | 0.4534 | 0.0923 |  461 | 6265 | 4440 |   70 |                     0.456  |

## Mean ± standard deviation across folds

| metric      |   mean |    std |    min |    max |
|:------------|-------:|-------:|-------:|-------:|
| roc_auc     | 0.6348 | 0.1269 | 0.4975 | 0.7477 |
| pr_auc      | 0.0692 | 0.0242 | 0.0541 | 0.0971 |
| brier_score | 0.1253 | 0.0641 | 0.082  | 0.199  |
| accuracy    | 0.5734 | 0.0542 | 0.5113 | 0.6105 |
| precision   | 0.068  | 0.0225 | 0.0548 | 0.0941 |
| recall      | 0.6636 | 0.2501 | 0.3847 | 0.8682 |
| specificity | 0.5703 | 0.0619 | 0.5024 | 0.6234 |
| f1          | 0.1228 | 0.0408 | 0.0965 | 0.1697 |
| tss         | 0.2339 | 0.2227 | 0.0081 | 0.4534 |
| hss         | 0.043  | 0.0457 | 0.0021 | 0.0923 |
