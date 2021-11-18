#!/bin/bash

for lam in 0.1 1 2 10 20 50
do
    python cs285/scripts/run_hw5_awac.py --env_name PointmassEasy-v0 \
        --exp_name q4_awac_easy_unsupervised_lam${lam} --use_rnd \
        --unsupervised_exploration --awac_lambda=${lam} \
        --num_exploration_steps=20000
done
