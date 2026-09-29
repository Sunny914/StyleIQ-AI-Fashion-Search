# ProductIQ Search Evaluation Report

## Evaluation Identity
- report_name: productiq_search_evaluation_report
- report_version: 1.0.0
- evaluation_contract_version: 12.1.0

## Benchmark
- benchmark_name: productiq_search_benchmark_v1
- benchmark_version: 1.0.0
- benchmark_artifact_path: resources/evaluation/productiq_search_benchmark_v1.json
- query_count: 10

## Evaluation Configuration
- execution_top_k: 50
- evaluation_top_k: 50
- min_relevant_grade: 2
- k_values: [1, 5, 10, 20, 50]

## Variant Results
### productiq_search_baseline_bm25 (12.5)
- retrieval_index_mode: benchmark_scoped_slice_4912_docs
- query_count: 10
- mrr: 0.42972582972582973
- precision_at_10: 0.17

### productiq_search_baseline_rrf (12.5)
- retrieval_index_mode: benchmark_scoped_slice_4912_docs
- query_count: 10
- mrr: 0.4106442577030812
- precision_at_10: 0.17

### productiq_search_baseline_semantic (12.5)
- query_count: 10
- mrr: 0.11893939393939394
- precision_at_10: 0.04

### productiq_search_ranking_baseline_ranker (12.7)
- query_count: 10
- mrr: 0.4106442577030812
- precision_at_10: 0.17

### productiq_search_ranking_ltr (12.7)
- query_count: 10
- mrr: 0.08195584468823008
- precision_at_10: 0.05

### productiq_search_ranking_retrieval_order (12.7)
- query_count: 10
- mrr: 0.4106442577030812
- precision_at_10: 0.17

## Pairwise Comparisons

- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@1: ref=0.4 cand=0.3 delta=-0.10000000000000003
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@5: ref=0.4 cand=0.5 delta=0.09999999999999998
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@10: ref=0.5 cand=0.5 delta=0.0
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@20: ref=0.7 cand=0.6 delta=-0.09999999999999998
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@50: ref=0.8 cand=0.7 delta=-0.10000000000000009
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf mrr: ref=0.42972582972582973 cand=0.4106442577030812 delta=-0.019081572022748516
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@1: ref=0.4 cand=0.3 delta=-0.10000000000000003
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@5: ref=0.34692787260227564 cand=0.3202908625906088 delta=-0.02663701001166685
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@10: ref=0.3610545698882585 cand=0.3436773330363454 delta=-0.017377236851913114
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@20: ref=0.4089329789146756 cand=0.35493122191589216 delta=-0.05400175699878346
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@50: ref=0.4328282233143108 cand=0.3810422447039513 delta=-0.051785978610359495
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@1: ref=0.4 cand=0.3 delta=-0.10000000000000003
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@5: ref=0.26 cand=0.24 delta=-0.020000000000000018
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@10: ref=0.17 cand=0.17 delta=0.0
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@20: ref=0.10500000000000001 cand=0.09 delta=-0.015000000000000013
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@50: ref=0.048 cand=0.041999999999999996 delta=-0.006000000000000005
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@1: ref=0.11583333333333332 cand=0.06583333333333333 delta=-0.04999999999999999
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@5: ref=0.29583333333333334 cand=0.3058333333333333 delta=0.009999999999999953
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@10: ref=0.36666666666666664 cand=0.38333333333333336 delta=0.01666666666666672
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@20: ref=0.5 cand=0.4166666666666667 delta=-0.08333333333333331
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@50: ref=0.5866666666666667 cand=0.5 delta=-0.08666666666666667
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@1: ref=0.4 cand=0.09999999999999998 delta=-0.30000000000000004
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@5: ref=0.4 cand=0.09999999999999998 delta=-0.30000000000000004
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@10: ref=0.5 cand=0.2 delta=-0.3
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@20: ref=0.7 cand=0.2 delta=-0.49999999999999994
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@50: ref=0.8 cand=0.30000000000000004 delta=-0.5
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic mrr: ref=0.42972582972582973 cand=0.11893939393939396 delta=-0.3107864357864358
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@1: ref=0.4 cand=0.09999999999999998 delta=-0.30000000000000004
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@5: ref=0.34692787260227564 cand=0.05531464700081434 delta=-0.2916132256014613
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@10: ref=0.3610545698882585 cand=0.07163633171044209 delta=-0.2894182381778164
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@20: ref=0.4089329789146756 cand=0.08386935597400791 delta=-0.3250636229406677
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@50: ref=0.4328282233143108 cand=0.1152110896300444 delta=-0.3176171336842664
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@1: ref=0.4 cand=0.09999999999999998 delta=-0.30000000000000004
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@5: ref=0.26 cand=0.04000000000000001 delta=-0.22
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@10: ref=0.17 cand=0.04000000000000001 delta=-0.13
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@20: ref=0.10500000000000001 cand=0.03 delta=-0.07500000000000001
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@50: ref=0.048 cand=0.022 delta=-0.026000000000000002
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@1: ref=0.11583333333333332 cand=0.020000000000000004 delta=-0.09583333333333331
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@5: ref=0.29583333333333334 cand=0.03999999999999998 delta=-0.25583333333333336
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@10: ref=0.36666666666666664 cand=0.065 delta=-0.30166666666666664
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@20: ref=0.5 cand=0.08999999999999997 delta=-0.41000000000000003
- [baseline_experiment] productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@50: ref=0.5866666666666667 cand=0.19 delta=-0.39666666666666667
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@1: ref=0.3 cand=0.3 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@5: ref=0.5 cand=0.5 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@10: ref=0.5 cand=0.5 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@20: ref=0.6 cand=0.6 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@50: ref=0.7 cand=0.7 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker mrr: ref=0.4106442577030812 cand=0.4106442577030812 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@1: ref=0.3 cand=0.3 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@5: ref=0.3202908625906088 cand=0.3202908625906088 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@10: ref=0.3436773330363454 cand=0.3436773330363454 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@20: ref=0.35493122191589216 cand=0.35493122191589216 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@50: ref=0.3810422447039513 cand=0.3810422447039513 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@1: ref=0.3 cand=0.3 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@5: ref=0.24 cand=0.24 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@10: ref=0.17 cand=0.17 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@20: ref=0.09 cand=0.09 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@50: ref=0.041999999999999996 cand=0.041999999999999996 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@1: ref=0.06583333333333333 cand=0.06583333333333333 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@5: ref=0.3058333333333333 cand=0.3058333333333333 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@10: ref=0.38333333333333336 cand=0.38333333333333336 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@20: ref=0.4166666666666667 cand=0.4166666666666667 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@50: ref=0.5 cand=0.5 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@1: ref=0.3 cand=0.0 delta=-0.3
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@5: ref=0.5 cand=0.09999999999999998 delta=-0.4
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@10: ref=0.5 cand=0.2 delta=-0.3
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@20: ref=0.6 cand=0.4 delta=-0.19999999999999996
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@50: ref=0.7 cand=0.7 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr mrr: ref=0.4106442577030812 cand=0.08195584468823008 delta=-0.32868841301485113
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@1: ref=0.3 cand=0.0 delta=-0.3
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@5: ref=0.3202908625906088 cand=0.07328286204777912 delta=-0.24700800054282968
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@10: ref=0.3436773330363454 cand=0.08820887996390847 delta=-0.25546845307243693
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@20: ref=0.35493122191589216 cand=0.14772814962495973 delta=-0.20720307229093243
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@50: ref=0.3810422447039513 cand=0.215042719958858 delta=-0.16599952474509333
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@1: ref=0.3 cand=0.0 delta=-0.3
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@5: ref=0.24 cand=0.06 delta=-0.18
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@10: ref=0.17 cand=0.05 delta=-0.12000000000000001
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@20: ref=0.09 cand=0.06 delta=-0.03
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@50: ref=0.041999999999999996 cand=0.041999999999999996 delta=0.0
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@1: ref=0.06583333333333333 cand=0.0 delta=-0.06583333333333333
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@5: ref=0.3058333333333333 cand=0.1 delta=-0.20583333333333328
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@10: ref=0.38333333333333336 cand=0.125 delta=-0.25833333333333336
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@20: ref=0.4166666666666667 cand=0.27083333333333337 delta=-0.14583333333333331
- [ranking_experiment] productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@50: ref=0.5 cand=0.5 delta=0.0

## Failure Analysis

- failure_record_count: 1320
- retrieval_pattern BM25_ONLY: 13
- retrieval_pattern NOT_RETRIEVED_BY_EITHER: 20
- retrieval_pattern RETRIEVED_BY_BOTH: 11

## Statistical Analysis

- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@1: delta=-0.1 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@5: delta=0.1 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@10: delta=0.0 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@20: delta=-0.1 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf hit_rate_at_k@50: delta=-0.1 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf mrr: delta=-0.01908157202274849 p=0.5223880597014925
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@1: delta=-0.1 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@5: delta=-0.02663701001166686 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@10: delta=-0.01737723685191313 p=0.736318407960199
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@20: delta=-0.054001756998783436 p=0.3582089552238806
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf ndcg_at_k@50: delta=-0.05178597861035953 p=0.2835820895522388
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@1: delta=-0.1 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@5: delta=-0.02 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@10: delta=0.0 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@20: delta=-0.015 p=0.5373134328358209
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf precision_at_k@50: delta=-0.006 p=0.5124378109452736
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@1: delta=-0.05 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@5: delta=0.009999999999999998 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@10: delta=0.01666666666666667 p=1.0
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@20: delta=-0.08333333333333334 p=0.5373134328358209
- productiq_search_baseline_bm25 -> productiq_search_baseline_rrf recall_at_k@50: delta=-0.08666666666666667 p=0.5124378109452736
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@1: delta=-0.3 p=0.25870646766169153
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@5: delta=-0.3 p=0.25870646766169153
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@10: delta=-0.3 p=0.26865671641791045
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@20: delta=-0.5 p=0.1044776119402985
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic hit_rate_at_k@50: delta=-0.5 p=0.06965174129353234
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic mrr: delta=-0.3107864357864358 p=0.01990049751243781
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@1: delta=-0.3 p=0.25870646766169153
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@5: delta=-0.2916132256014613 p=0.17412935323383086
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@10: delta=-0.2894182381778164 p=0.0945273631840796
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@20: delta=-0.3250636229406677 p=0.03482587064676617
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic ndcg_at_k@50: delta=-0.3176171336842664 p=0.014925373134328358
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@1: delta=-0.3 p=0.25870646766169153
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@5: delta=-0.22000000000000003 p=0.17412935323383086
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@10: delta=-0.13 p=0.0945273631840796
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@20: delta=-0.075 p=0.03482587064676617
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic precision_at_k@50: delta=-0.026000000000000002 p=0.029850746268656716
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@1: delta=-0.09583333333333333 p=0.25870646766169153
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@5: delta=-0.2558333333333333 p=0.17412935323383086
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@10: delta=-0.30166666666666664 p=0.0945273631840796
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@20: delta=-0.41 p=0.03482587064676617
- productiq_search_baseline_bm25 -> productiq_search_baseline_semantic recall_at_k@50: delta=-0.39666666666666667 p=0.029850746268656716
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@1: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@5: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@10: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@20: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker hit_rate_at_k@50: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker mrr: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@1: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@5: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@10: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@20: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker ndcg_at_k@50: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@1: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@5: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@10: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@20: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker precision_at_k@50: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@1: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@5: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@10: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@20: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_baseline_ranker recall_at_k@50: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@1: delta=-0.3 p=0.26865671641791045
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@5: delta=-0.4 p=0.25870646766169153
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@10: delta=-0.3 p=0.42786069651741293
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@20: delta=-0.2 p=0.5422885572139303
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr hit_rate_at_k@50: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr mrr: delta=-0.3286884130148512 p=0.08955223880597014
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@1: delta=-0.3 p=0.26865671641791045
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@5: delta=-0.24700800054282968 p=0.22885572139303484
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@10: delta=-0.25546845307243693 p=0.20398009950248755
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@20: delta=-0.20720307229093246 p=0.23880597014925373
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr ndcg_at_k@50: delta=-0.16599952474509325 p=0.18407960199004975
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@1: delta=-0.3 p=0.26865671641791045
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@5: delta=-0.18 p=0.32338308457711445
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@10: delta=-0.12000000000000002 p=0.29850746268656714
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@20: delta=-0.030000000000000006 p=0.5572139303482587
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr precision_at_k@50: delta=0.0 p=1.0
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@1: delta=-0.06583333333333333 p=0.26865671641791045
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@5: delta=-0.2058333333333333 p=0.3781094527363184
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@10: delta=-0.25833333333333336 p=0.2885572139303483
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@20: delta=-0.14583333333333331 p=0.43283582089552236
- productiq_search_ranking_retrieval_order -> productiq_search_ranking_ltr recall_at_k@50: delta=0.0 p=1.0

## Reproducibility

- catalog_artifact: resources/processed/product_representations.parquet
- source_representation_checksum: 7fc2b6c08ef03233bdae1c845f4a087cd578fdb6d861b7d64ec72c71e92c3379
- ltr_artifact_path: resources/models/ranking_ltr_reference_v10_7_0
- ltr_artifact_present: True
- retrieval_index_mode[productiq_search_baseline_bm25]: benchmark_scoped_slice_4912_docs
- retrieval_index_mode[productiq_search_baseline_rrf]: benchmark_scoped_slice_4912_docs

## Limitations

- Report values are copied from persisted Phase 12 artifacts; metrics are not recomputed.
- No winner, best variant, recommended, promotion, or deployment decision is selected.
- BM25 baseline runs may use benchmark-scoped retrieval slices rather than full-catalog BM25.
- RRF baseline may inherit scoped BM25 retrieval provenance.
- LTR ranking results depend on a local Phase 10.7 reference artifact at resources/models/ranking_ltr_reference_v10_7_0; fresh clones may need retraining or explicit artifact supply.
- Statistical summaries reflect the curated 10-query benchmark sample only.
- Variant uses retrieval_index_mode='benchmark_scoped_slice_4912_docs'; not a full-catalog BM25 baseline.
