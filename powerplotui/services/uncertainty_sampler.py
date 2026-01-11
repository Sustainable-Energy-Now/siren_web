"""
Uncertainty Sampler for Monte Carlo Simulations

This module provides utility classes for sampling from various probability distributions
used in the Monte Carlo simulation for renewable energy target analysis.

All methods are optimized for vectorized NumPy operations to handle 100,000+ iterations efficiently.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)


class UncertaintySampler:
    """
    Utility class for sampling from various probability distributions.
    Optimized for vectorized NumPy operations.
    """

    # Commissioning probability profiles
    # These define the probability that a facility at each status level
    # will actually be commissioned by the target year
    PROBABILITY_PROFILES = {
        'optimistic': {
            'commissioned': 1.00,       # Already operating
            'under_construction': 1.00,  # Very likely to complete
            'planned': 0.95,             # High confidence
            'probable': 0.70,            # Good chance
            'possible': 0.40,            # Moderate chance
        },
        'balanced': {
            'commissioned': 1.00,
            'under_construction': 0.95,
            'planned': 0.80,
            'probable': 0.50,
            'possible': 0.20,
        },
        'conservative': {
            'commissioned': 1.00,
            'under_construction': 0.85,
            'planned': 0.60,
            'probable': 0.30,
            'possible': 0.10,
        },
    }

    @staticmethod
    def sample_commissioning(status_array, profile='optimistic', n_iterations=100000):
        """
        Vectorized commissioning probability sampling using Bernoulli distribution.

        For each facility, samples whether it will be commissioned based on its status.
        Uses a Bernoulli trial: commissioned if random() < probability[status].

        Args:
            status_array: 1D numpy array of status strings (e.g., ['planned', 'probable', ...])
            profile: str, one of 'optimistic', 'balanced', 'conservative'
            n_iterations: int, number of Monte Carlo iterations

        Returns:
            2D numpy array of shape (n_iterations, n_facilities) with boolean values
            True = facility commissioned in that iteration
        """
        if profile not in UncertaintySampler.PROBABILITY_PROFILES:
            raise ValueError(f"Invalid profile '{profile}'. Choose from {list(UncertaintySampler.PROBABILITY_PROFILES.keys())}")

        probabilities = UncertaintySampler.PROBABILITY_PROFILES[profile]
        n_facilities = len(status_array)

        # Map each status to its probability
        # Handle case-insensitive matching and missing statuses
        prob_array = np.array([
            probabilities.get(status.lower(), 0.5)  # Default to 50% if status unknown
            for status in status_array
        ])

        # Generate random numbers for all facilities and iterations
        # Shape: (n_iterations, n_facilities)
        random_matrix = np.random.random((n_iterations, n_facilities))

        # Commission if random < probability (broadcast comparison)
        commissioned = random_matrix < prob_array[np.newaxis, :]

        logger.debug(f"Sampled commissioning for {n_facilities} facilities across {n_iterations} iterations")
        logger.debug(f"Using {profile} profile: {probabilities}")

        return commissioned

    @staticmethod
    def sample_uniform_delay(n_facilities, n_iterations=100000, min_months=0, max_months=24):
        """
        Sample commissioning delays uniformly between min and max months.

        Models the uncertainty in when facilities will actually commission.
        Even committed projects often experience delays.

        Args:
            n_facilities: int, number of facilities in pipeline
            n_iterations: int, number of Monte Carlo iterations
            min_months: int, minimum delay in months (default 0)
            max_months: int, maximum delay in months (default 24)

        Returns:
            2D numpy array of shape (n_iterations, n_facilities) with delay values in months
        """
        delays = np.random.uniform(
            low=min_months,
            high=max_months,
            size=(n_iterations, n_facilities)
        )

        logger.debug(f"Sampled delays for {n_facilities} facilities: uniform({min_months}, {max_months}) months")

        return delays

    @staticmethod
    def sample_normal_cf(mean_array, std_array, n_iterations=100000, min_cf=0.0, max_cf=1.0):
        """
        Sample capacity factors from normal distributions (clipped to realistic bounds).

        Models year-to-year variability in renewable generation due to weather.
        Each technology has its own mean and standard deviation.

        Args:
            mean_array: 1D numpy array of mean capacity factors per facility
            std_array: 1D numpy array of std dev capacity factors per facility
            n_iterations: int, number of Monte Carlo iterations
            min_cf: float, minimum allowed capacity factor (default 0.0)
            max_cf: float, maximum allowed capacity factor (default 1.0)

        Returns:
            2D numpy array of shape (n_iterations, n_facilities) with CF values
        """
        n_facilities = len(mean_array)

        # Sample from normal distribution for all iterations and facilities
        # Shape: (n_iterations, n_facilities)
        cf_samples = np.random.normal(
            loc=mean_array[np.newaxis, :],  # Broadcast mean to all iterations
            scale=std_array[np.newaxis, :],  # Broadcast std to all iterations
            size=(n_iterations, n_facilities)
        )

        # Clip to realistic bounds (CFs must be between 0 and 1)
        cf_samples = np.clip(cf_samples, min_cf, max_cf)

        logger.debug(f"Sampled capacity factors for {n_facilities} facilities")
        logger.debug(f"Mean CF range: {mean_array.min():.3f} - {mean_array.max():.3f}")
        logger.debug(f"Std dev range: {std_array.min():.3f} - {std_array.max():.3f}")

        return cf_samples

    @staticmethod
    def sample_demand_uncertainty(base_demand, uncertainty_pct=0.20, n_iterations=100000):
        """
        Sample demand with uniform ±X% uncertainty around base projection.

        Models uncertainty in future demand growth due to:
        - Economic growth variations
        - Electrification adoption rates
        - Energy efficiency improvements

        Args:
            base_demand: float, base demand projection in GWh
            uncertainty_pct: float, uncertainty as decimal (0.20 = ±20%)
            n_iterations: int, number of Monte Carlo iterations

        Returns:
            1D numpy array of shape (n_iterations,) with demand values in GWh
        """
        lower_bound = base_demand * (1 - uncertainty_pct)
        upper_bound = base_demand * (1 + uncertainty_pct)

        demand_samples = np.random.uniform(
            low=lower_bound,
            high=upper_bound,
            size=n_iterations
        )

        logger.debug(f"Sampled demand with ±{uncertainty_pct*100:.0f}% uncertainty")
        logger.debug(f"Base demand: {base_demand:.1f} GWh")
        logger.debug(f"Range: {lower_bound:.1f} - {upper_bound:.1f} GWh")

        return demand_samples

    @staticmethod
    def get_probability_for_status(status, profile='optimistic'):
        """
        Get the commissioning probability for a specific status level.

        Utility method for reporting and parameter logging.

        Args:
            status: str, facility status (e.g., 'planned', 'probable')
            profile: str, probability profile name

        Returns:
            float, probability (0.0 to 1.0)
        """
        if profile not in UncertaintySampler.PROBABILITY_PROFILES:
            raise ValueError(f"Invalid profile '{profile}'")

        return UncertaintySampler.PROBABILITY_PROFILES[profile].get(status.lower(), 0.5)

    @staticmethod
    def validate_samples(samples, expected_shape, sample_name="samples"):
        """
        Validate sampled array has correct shape and valid values.

        Args:
            samples: numpy array to validate
            expected_shape: tuple, expected array shape
            sample_name: str, name for error messages

        Raises:
            ValueError if validation fails
        """
        if samples.shape != expected_shape:
            raise ValueError(
                f"{sample_name} has shape {samples.shape}, expected {expected_shape}"
            )

        if np.isnan(samples).any():
            raise ValueError(f"{sample_name} contains NaN values")

        if np.isinf(samples).any():
            raise ValueError(f"{sample_name} contains infinite values")

        logger.debug(f"Validated {sample_name}: shape {samples.shape}, range [{samples.min():.3f}, {samples.max():.3f}]")