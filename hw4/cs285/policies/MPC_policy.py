import numpy as np

from .base_policy import BasePolicy


class MPCPolicy(BasePolicy):

    def __init__(self,
                 env,
                 ac_dim,
                 dyn_models,
                 horizon,
                 N,
                 sample_strategy='random',
                 cem_iterations=4,
                 cem_num_elites=5,
                 cem_alpha=1,
                 **kwargs
                 ):
        super().__init__(**kwargs)

        # init vars
        self.env = env
        self.dyn_models = dyn_models
        self.horizon = horizon
        self.N = N
        self.data_statistics = None  # NOTE must be updated from elsewhere

        self.ob_dim = self.env.observation_space.shape[0]

        # action space
        self.ac_space = self.env.action_space
        self.ac_dim = ac_dim
        self.low = self.ac_space.low
        self.high = self.ac_space.high

        # Sampling strategy
        allowed_sampling = ('random', 'cem')
        assert sample_strategy in allowed_sampling, f"sample_strategy must be one of the following: {allowed_sampling}"
        self.sample_strategy = sample_strategy
        self.cem_iterations = cem_iterations
        self.cem_num_elites = cem_num_elites
        self.cem_alpha = cem_alpha

        print(f"Using action sampling strategy: {self.sample_strategy}")
        if self.sample_strategy == 'cem':
            print(f"CEM params: alpha={self.cem_alpha}, "
                + f"num_elites={self.cem_num_elites}, iterations={self.cem_iterations}")

    def sample_action_sequences(self, num_sequences, horizon, obs=None):
        if self.sample_strategy == 'random' \
            or (self.sample_strategy == 'cem' and obs is None):
            # TODO(Q1) uniformly sample trajectories and return an array of
            # dimensions (num_sequences, horizon, self.ac_dim) in the range
            # [self.low, self.high]
            random_action_sequences = np.random.uniform(low=self.low, high=self.high, size=(num_sequences, horizon, self.ac_dim))
            return random_action_sequences
        elif self.sample_strategy == 'cem':
            # TODO(Q5): Implement action selection using CEM.
            # Begin with randomly selected actions, then refine the sampling distribution
            # iteratively as described in Section 3.3, "Iterative Random-Shooting with Refinement" of
            # https://arxiv.org/pdf/1909.11652.pdf
            for i in range(self.cem_iterations):
                # - Sample candidate sequences from a Gaussian with the current
                #   elite mean and variance
                #     (Hint: remember that for the first iteration, we instead sample
                #      uniformly at random just like we do for random-shooting)
                # - Get the top `self.cem_num_elites` elites
                #     (Hint: what existing function can we use to compute rewards for
                #      our candidate sequences in order to rank them?)
                # - Update the elite mean and variance
                if i == 0:
                    sampled_action_sequences = np.random.uniform(low=self.low, high=self.high, size=(num_sequences, horizon, self.ac_dim))
                else:
                    sampled_action_sequences = np.random.normal(loc=running_mean, scale=np.sqrt(running_var), size=(num_sequences, horizon, self.ac_dim))
                all_rewards = self.evaluate_candidate_sequences(sampled_action_sequences, obs)
                elites_indices = all_rewards.argsort()[-self.cem_num_elites:]
                if i == 0:
                    running_mean = np.mean(sampled_action_sequences[elites_indices, :, :], axis=0) # The mean matrix is of shape (horizon, self.ac_dim)
                    running_var = np.var(sampled_action_sequences[elites_indices, :, :], axis=0) # The var matrix is of shape (horizon, self.ac_dim)
                else:
                    running_mean = self.cem_alpha * np.mean(sampled_action_sequences[elites_indices, :, :], axis=0) + (1-self.cem_alpha) * running_mean
                    running_var = self.cem_alpha * np.var(sampled_action_sequences[elites_indices, :, :], axis=0) + (1-self.cem_alpha) * running_var
            # TODO(Q5): Set `cem_action` to the appropriate action sequence chosen by CEM.
            # The shape should be (horizon, self.ac_dim)
            # best_action_index = all_rewards.argsort()[-1]
            # cem_action = sampled_action_sequences[best_action_index]
            cem_action = np.mean(sampled_action_sequences[elites_indices, :, :], axis=0)
        
            # alternative implementation
            # running_mean, running_var = np.zeros((self.horizon, self.ac_dim)), np.zeros((self.horizon, self.ac_dim, self.ac_dim))
            # for i in range(self.cem_iterations):
            #     if i == 0:
            #         sampled_action_sequences = np.random.uniform(low=self.low, high=self.high, size=(num_sequences, horizon, self.ac_dim))
            #     else:
            #         for t in range(horizon):
            #             sampled_action_sequences[:, t, :] = np.random.multivariate_normal(running_mean[t], running_var[t], size=num_sequences)
            #     all_rewards = self.evaluate_candidate_sequences(sampled_action_sequences, obs)
            #     elites_indices = all_rewards.argsort()[-self.cem_num_elites:]
            #     elite_actions = np.take(sampled_action_sequences, elites_indices, 0)
            #     for t in range(horizon):
            #         running_mean[t] = self.cem_alpha * np.mean(np.transpose(elite_actions[:, t, :]), axis=1) + (1-self.cem_alpha) * running_mean[t] # The mean matrix is of shape (horizon, self.ac_dim)
            #         running_var[t] = self.cem_alpha * np.cov(np.transpose(elite_actions[:, t, :])) + (1-self.cem_alpha) * running_var[t] # The var matrix is of shape (horizon, self.ac_dim, self.ac_dim)
            # # best_action_index = all_rewards.argsort()[-1]
            # # cem_action = sampled_action_sequences[best_action_index]
            # cem_action = np.mean(elite_actions, axis=0)

            return cem_action[None] # add an axis to the first dimension
        else:
            raise Exception(f"Invalid sample_strategy: {self.sample_strategy}")

    def evaluate_candidate_sequences(self, candidate_action_sequences, obs):
        # TODO(Q2): for each model in ensemble, compute the predicted sum of rewards
        # for each candidate action sequence.
        #
        # Then, return the mean predictions across all ensembles.
        # Hint: the return value should be an array of shape (N,)
        num_sequences = candidate_action_sequences.shape[0]
        rewards_action_sequences_running_sum_for_ensemble = np.zeros((num_sequences,))
        for model in self.dyn_models:
            rewards_action_sequences_running_sum_for_ensemble += self.calculate_sum_of_rewards(obs, candidate_action_sequences, model)

        # Alternative way:    
        # # for each model in ensemble:
        # predicted_sum_of_rewards_per_model = []
        # for model in self.dyn_models:
        #     sum_of_rewards = self.calculate_sum_of_rewards(
        #         obs, candidate_action_sequences, model)
        #     predicted_sum_of_rewards_per_model.append(sum_of_rewards)

        # # calculate mean_across_ensembles(predicted rewards)
        # predicted_rewards = np.mean(
        #     predicted_sum_of_rewards_per_model, axis=0)  # [ens, N] --> N

        return rewards_action_sequences_running_sum_for_ensemble / num_sequences

    def get_action(self, obs):
        if self.data_statistics is None:
            return self.sample_action_sequences(num_sequences=1, horizon=1)[0]

        # sample random actions (N x horizon)
        candidate_action_sequences = self.sample_action_sequences(
            num_sequences=self.N, horizon=self.horizon, obs=obs)

        if candidate_action_sequences.shape[0] == 1:
            # CEM: only a single action sequence to consider; return the first action
            return candidate_action_sequences[0][0][None]
        else:
            predicted_rewards = self.evaluate_candidate_sequences(candidate_action_sequences, obs)

            # pick the action sequence and return the 1st element of that sequence
            best_action_sequence = candidate_action_sequences[np.argmax(predicted_rewards)]  # TODO (Q2)
            action_to_take = best_action_sequence[0]  # TODO (Q2)
            # a[None] is equivalent to a[None, :, :] or a[None, ...] or a[np.newaxis, :, :] (add an axis in the first dimension)
            return action_to_take[None]  # Unsqueeze the first index 

    def calculate_sum_of_rewards(self, obs, candidate_action_sequences, model):
        """

        :param obs: numpy array with the current observation. Shape [D_obs]
        :param candidate_action_sequences: numpy array with the candidate action
        sequences. Shape [N, H, D_action] where
            - N is the number of action sequences considered
            - H is the horizon
            - D_action is the action of the dimension
        :param model: The current dynamics model.
        :return: numpy array with the sum of rewards for each action sequence.
        The array should have shape [N].
        """
        N = candidate_action_sequences.shape[0]
        sum_of_rewards = np.zeros(N)  # TODO (Q2)
        # For each candidate action sequence, predict a sequence of
        # states for each dynamics model in your ensemble.
        # Once you have a sequence of predicted states from each model in
        # your ensemble, calculate the sum of rewards for each sequence
        # using `self.env.get_reward(predicted_obs, action)` at each step.
        # You should sum across `self.horizon` time step.
        # Hint: you should use model.get_prediction and you shouldn't need
        #       to import pytorch in this file.
        # Hint: Remember that the model can process observations and actions
        #       in batch, which can be much faster than looping through each
        #       action sequence.
        assert candidate_action_sequences.shape[1] == self.horizon
        obs = np.tile(obs, (N, 1)) # repeat the current observation vertically
        for t in range(self.horizon):
            actions = candidate_action_sequences[:, t, :]
            rewards, dones = self.env.get_reward(obs, actions)
            sum_of_rewards += rewards
            obs = model.get_prediction(obs, actions, self.data_statistics)

        return sum_of_rewards
