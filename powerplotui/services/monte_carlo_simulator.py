"""
Monte Carlo Simulator for 2040 Renewable Energy Target Probability Analysis

This module implements a Monte Carlo simulation to calculate the probability
of achieving renewable energy targets by 2040 in the South West Interconnected System (SWIS).

The simulation models four key uncertainties:
1. Facility commissioning probability (will projects actually get built?)
2. Commissioning date delays (when will they come online?)
3. Capacity factor variability (weather-driven generation variations)
4. Demand growth uncertainty (future electricity demand)

Uses vectorized NumPy operations to run 100,000+ iterations efficiently.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from django.db.models import Sum, Q
import time

from .uncertainty_sampler import UncertaintySampler
from .capacity_factor_analyzer import CapacityFactorAnalyzer

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """
    Monte Carlo simulation for 2040 renewable energy target probability analysis.

    Workflow:
    1. Initialize with scenario and parameters
    2. Load historical data for capacity factor distributions
    3. Load pipeline facilities and demand factors
    4. Run vectorized iterations (batched for memory efficiency)
    5. Calculate statistics and store results
    """

    def __init__(self, target_scenario, num_iterations=100000,
                 probability_profile='optimistic', target_year=2040):
        """
        Initialize simulator with scenario and parameters.

        Args:
            target_scenario: TargetScenario model instance
            num_iterations: int, number of Monte Carlo iterations
            probability_profile: str, 'optimistic', 'balanced', or 'conservative'
            target_year: int, year to project to (default 2040)
        """
        self.target_scenario = target_scenario
        self.num_iterations = num_iterations
        self.probability_profile = probability_profile
        self.target_year = target_year

        # Batch size for processing iterations
        # Process in chunks to manage memory
        self.batch_size = 10000

        # Data containers (loaded lazily)
        self.cf_distributions = None
        self.pipeline_df = None
        self.base_demand_2040 = None

        logger.info(f"Initialized MonteCarloSimulator: {num_iterations} iterations, {probability_profile} profile")

    def run_simulation(self, simulation_record):
        """
        Main entry point - runs full simulation and updates database.

        Args:
            simulation_record: MonteCarloSimulation model instance

        Returns:
            MonteCarloSimulation record (updated with results)
        """
        from siren_web.models import MonteCarloParameter, MonteCarloResult

        logger.info(f"Starting Monte Carlo simulation ID {simulation_record.simulation_id}")
        start_time = time.time()

        try:
            # Update status
            simulation_record.status = 'running'
            simulation_record.save(update_fields=['status'])

            # Step 1: Load data
            logger.info("Step 1: Loading capacity factor distributions...")
            self.cf_distributions = self._load_capacity_factor_distributions()
            self._store_parameters(simulation_record, 'capacity_factor', self.cf_distributions,
                                 "Capacity factor distributions by technology")

            logger.info("Step 2: Loading pipeline facilities...")
            self.pipeline_df = self._load_pipeline_facilities()
            logger.info(f"  Loaded {len(self.pipeline_df)} pipeline facilities")

            logger.info("Step 3: Calculating base demand projection...")
            self.base_demand_2040 = self._calculate_base_demand()
            self._store_parameters(simulation_record, 'demand_growth',
                                 {'base_demand_2040_gwh': self.base_demand_2040},
                                 "Base 2040 demand projection")

            # Step 4: Store commissioning probabilities
            commissioning_probs = {
                status: UncertaintySampler.get_probability_for_status(status, self.probability_profile)
                for status in ['commissioned', 'under_construction', 'planned', 'probable', 'possible']
            }
            self._store_parameters(simulation_record, 'commissioning_probability', commissioning_probs,
                                 f"{self.probability_profile.capitalize()} commissioning probability profile")

            # Step 5: Store delay distribution
            self._store_parameters(simulation_record, 'delay_distribution',
                                 {'min_months': 0, 'max_months': 24, 'distribution': 'uniform'},
                                 "Commissioning delay distribution")

            # Step 6: Run Monte Carlo iterations
            logger.info(f"Step 4: Running {self.num_iterations} Monte Carlo iterations...")
            re_percentage_results = self._run_iterations()

            # Step 7: Calculate statistics
            logger.info("Step 5: Calculating statistics...")
            stats = self._calculate_statistics(re_percentage_results)

            # Step 8: Store results
            logger.info("Step 6: Storing results...")
            self._store_results(simulation_record, re_percentage_results, stats)

            # Update execution time
            execution_time = time.time() - start_time
            simulation_record.execution_time_seconds = execution_time

            logger.info(f"Monte Carlo simulation completed in {execution_time:.1f}s")
            logger.info(f"  Mean RE%: {stats['mean_re_percentage']:.2f}%")
            logger.info(f"  90% CI: [{stats['p10_re_percentage']:.2f}%, {stats['p90_re_percentage']:.2f}%]")
            logger.info(f"  P(75% target): {stats['probability_75_percent']:.1f}%")
            logger.info(f"  P(85% target): {stats['probability_85_percent']:.1f}%")

            return simulation_record

        except Exception as e:
            logger.error(f"Monte Carlo simulation failed: {e}", exc_info=True)
            simulation_record.status = 'failed'
            simulation_record.error_message = str(e)
            simulation_record.execution_time_seconds = time.time() - start_time
            simulation_record.save()
            raise

    def _load_capacity_factor_distributions(self):
        """
        Calculate mean and std dev for each technology from MonthlyREPerformance.

        Returns:
            dict: {technology: {'mean': X, 'std': Y, 'min': A, 'max': B}}
        """
        analyzer = CapacityFactorAnalyzer()
        distributions = analyzer.calculate_technology_distributions()
        analyzer.validate_distributions(distributions)
        return distributions

    def _load_pipeline_facilities(self):
        """
        Load NewCapacityCommissioned records expected by target_year.

        Returns:
            DataFrame with columns: facility_code, capacity_mw, technology_type, status, expected_date
        """
        from siren_web.models import NewCapacityCommissioned

        # Query pipeline facilities
        pipeline_facilities = NewCapacityCommissioned.objects.filter(
            expected_commissioning_date__lte=date(self.target_year, 12, 31)
        ).select_related('facility').values(
            'facility__facility_code',
            'capacity_mw',
            'technology_type',
            'status',
            'expected_commissioning_date'
        )

        # Convert to DataFrame
        df = pd.DataFrame(list(pipeline_facilities))

        if df.empty:
            logger.warning("No pipeline facilities found - using empty DataFrame")
            return pd.DataFrame(columns=['facility_code', 'capacity_mw', 'technology_type', 'status', 'expected_date'])

        # Rename columns for convenience
        df = df.rename(columns={
            'facility__facility_code': 'facility_code',
            'expected_commissioning_date': 'expected_date'
        })

        # Normalize technology names
        analyzer = CapacityFactorAnalyzer()
        df['technology_normalized'] = df['technology_type'].apply(analyzer.normalize_technology_name)

        # Filter out Unknown technologies
        df = df[df['technology_normalized'] != 'Unknown'].copy()

        logger.debug(f"Pipeline facilities by technology:")
        for tech in df['technology_normalized'].unique():
            count = (df['technology_normalized'] == tech).sum()
            capacity = df[df['technology_normalized'] == tech]['capacity_mw'].sum()
            logger.debug(f"  {tech}: {count} facilities, {capacity:.1f} MW")

        return df

    def _calculate_base_demand(self):
        """
        Calculate base 2040 demand projection using existing methods.

        For now, uses a simplified approach. In future, could integrate with
        FactorBasedProjector for more sophisticated demand modeling.

        Returns:
            float, demand in GWh
        """
        from siren_web.models import MonthlyREPerformance

        # Get most recent annual demand
        try:
            recent_performance = MonthlyREPerformance.objects.filter(
                year__gte=2023
            ).order_by('-year', '-month').first()

            if recent_performance:
                # Use underlying demand (includes DPV)
                latest_year = recent_performance.year
                annual_demand_gwh = recent_performance.underlying_demand * 12  # Rough approximation

                # Simple growth projection: 2% annual growth to 2040
                years_ahead = self.target_year - latest_year
                growth_rate = 0.02
                projected_demand = annual_demand_gwh * ((1 + growth_rate) ** years_ahead)

                logger.info(f"Base {self.target_year} demand: {projected_demand:.1f} GWh "
                          f"(grown from {latest_year} at {growth_rate*100:.1f}%/yr)")

                return projected_demand

        except Exception as e:
            logger.warning(f"Could not calculate demand from MonthlyREPerformance: {e}")

        # Fallback: use typical SWIS annual demand
        fallback_demand = 25000.0  # GWh (approximate 2040 SWIS demand)
        logger.warning(f"Using fallback demand: {fallback_demand} GWh")
        return fallback_demand

    def _run_iterations(self):
        """
        Run all Monte Carlo iterations in batches.

        Returns:
            numpy array of shape (num_iterations,) with RE% results
        """
        n_batches = (self.num_iterations + self.batch_size - 1) // self.batch_size
        all_results = []

        for batch_idx in range(n_batches):
            batch_start = batch_idx * self.batch_size
            batch_end = min((batch_idx + 1) * self.batch_size, self.num_iterations)
            batch_size_actual = batch_end - batch_start

            logger.info(f"Processing batch {batch_idx + 1}/{n_batches} ({batch_size_actual} iterations)")

            batch_results = self._calculate_iteration_batch(batch_size_actual)
            all_results.append(batch_results)

        # Concatenate all batches
        return np.concatenate(all_results)

    def _calculate_iteration_batch(self, batch_size):
        """
        Calculate a batch of iterations using vectorized NumPy operations.

        Args:
            batch_size: int, number of iterations in this batch

        Returns:
            numpy array of shape (batch_size,) with RE% results
        """
        if self.pipeline_df.empty:
            # No pipeline facilities - return zero RE%
            logger.warning("No pipeline facilities - returning 0% RE")
            return np.zeros(batch_size)

        n_facilities = len(self.pipeline_df)

        # Sample uncertainties
        # 1. Commissioning: will facility be built? (n_iterations x n_facilities) boolean
        commissioned = UncertaintySampler.sample_commissioning(
            self.pipeline_df['status'].values,
            self.probability_profile,
            batch_size
        )

        # 2. Delays: how many months delayed? (n_iterations x n_facilities) float
        delays_months = UncertaintySampler.sample_uniform_delay(
            n_facilities,
            batch_size,
            min_months=0,
            max_months=24
        )

        # 3. Capacity factors: annual generation variation (n_iterations x n_facilities) float
        cf_samples = self._sample_capacity_factors(batch_size)

        # 4. Demand: total demand uncertainty (n_iterations,) float
        demand_samples = UncertaintySampler.sample_demand_uncertainty(
            self.base_demand_2040,
            uncertainty_pct=0.20,
            n_iterations=batch_size
        )

        # Calculate which facilities are commissioned by target year after delays
        commissioned_by_target = self._apply_delays(delays_months)

        # Effective commissioning = commissioned AND commissioned_by_target
        effective_commissioned = commissioned & commissioned_by_target

        # Calculate 2040 RE%
        re_percentage = self._calculate_re_percentage(
            effective_commissioned,
            cf_samples,
            demand_samples
        )

        return re_percentage

    def _sample_capacity_factors(self, batch_size):
        """
        Sample capacity factors for all facilities.

        Args:
            batch_size: int, number of iterations

        Returns:
            numpy array of shape (batch_size, n_facilities) with CF values
        """
        n_facilities = len(self.pipeline_df)

        # Get mean and std dev for each facility based on its technology
        mean_cfs = []
        std_cfs = []

        for _, facility in self.pipeline_df.iterrows():
            tech = facility['technology_normalized']
            dist = self.cf_distributions.get(tech, {'mean': 0.30, 'std': 0.10})
            mean_cfs.append(dist['mean'])
            std_cfs.append(dist['std'])

        mean_array = np.array(mean_cfs)
        std_array = np.array(std_cfs)

        # Sample capacity factors
        cf_samples = UncertaintySampler.sample_normal_cf(
            mean_array,
            std_array,
            n_iterations=batch_size
        )

        return cf_samples

    def _apply_delays(self, delays_months):
        """
        Check if facilities are still commissioned by target year after delays.

        Args:
            delays_months: numpy array (n_iterations, n_facilities) of delay values

        Returns:
            numpy array (n_iterations, n_facilities) of boolean values
        """
        n_iterations, n_facilities = delays_months.shape

        # Get expected commissioning dates
        expected_dates = pd.to_datetime(self.pipeline_df['expected_date'].values)

        # Convert to numpy datetime64
        expected_dates_np = expected_dates.values

        # Broadcast to all iterations: (1, n_facilities) -> (n_iterations, n_facilities)
        expected_dates_broadcast = np.tile(expected_dates_np, (n_iterations, 1))

        # Add delays (convert months to days, approximately)
        delays_days = delays_months * 30  # Rough conversion
        delayed_dates = expected_dates_broadcast + delays_days.astype('timedelta64[D]')

        # Check if commissioned by target year
        target_date = np.datetime64(f'{self.target_year}-12-31')
        commissioned_by_target = delayed_dates <= target_date

        return commissioned_by_target

    def _calculate_re_percentage(self, commissioned, cf_array, demand_array):
        """
        Calculate 2040 RE% for each iteration.

        Args:
            commissioned: numpy array (n_iterations, n_facilities) boolean
            cf_array: numpy array (n_iterations, n_facilities) float
            demand_array: numpy array (n_iterations,) float

        Returns:
            numpy array (n_iterations,) with RE% values
        """
        # Get capacity for each facility
        capacity_mw = self.pipeline_df['capacity_mw'].values  # (n_facilities,)

        # Calculate annual generation for each facility
        # Generation (GWh) = Capacity (MW) × CF × 8760 hours / 1000
        # Shape: (n_iterations, n_facilities)
        commissioned_capacity = commissioned * capacity_mw  # Broadcast capacity
        annual_generation_gwh = (commissioned_capacity * cf_array * 8760) / 1000

        # Sum across facilities to get total RE generation
        # Shape: (n_iterations,)
        total_re_generation = np.sum(annual_generation_gwh, axis=1)

        # Calculate RE percentage
        re_percentage = (total_re_generation / demand_array) * 100

        # Sanity check: clip to reasonable range
        re_percentage = np.clip(re_percentage, 0, 200)  # Max 200% (shouldn't happen but prevents outliers)

        return re_percentage

    def _calculate_statistics(self, re_percentage_results):
        """
        Calculate summary statistics from results array.

        Args:
            re_percentage_results: numpy array of RE% values

        Returns:
            dict with statistics
        """
        # Percentiles
        percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentile_values = np.percentile(re_percentage_results, percentiles)

        # Target probabilities
        prob_75 = (re_percentage_results >= 75).sum() / len(re_percentage_results) * 100
        prob_85 = (re_percentage_results >= 85).sum() / len(re_percentage_results) * 100

        stats = {
            'mean_re_percentage': float(np.mean(re_percentage_results)),
            'median_re_percentage': float(np.median(re_percentage_results)),
            'p10_re_percentage': float(percentile_values[2]),  # 10th percentile
            'p90_re_percentage': float(percentile_values[6]),  # 90th percentile
            'std_dev_re_percentage': float(np.std(re_percentage_results)),
            'probability_75_percent': float(prob_75),
            'probability_85_percent': float(prob_85),
            'percentiles': {f'p{p}': float(percentile_values[i]) for i, p in enumerate(percentiles)},
        }

        return stats

    def _store_results(self, simulation_record, re_percentage_results, stats):
        """
        Store results in MonteCarloSimulation and MonteCarloResult models.

        Args:
            simulation_record: MonteCarloSimulation instance
            re_percentage_results: numpy array of results
            stats: dict of statistics
        """
        from siren_web.models import MonteCarloResult

        # Update simulation record with summary stats
        simulation_record.mean_re_percentage = stats['mean_re_percentage']
        simulation_record.median_re_percentage = stats['median_re_percentage']
        simulation_record.p10_re_percentage = stats['p10_re_percentage']
        simulation_record.p90_re_percentage = stats['p90_re_percentage']
        simulation_record.std_dev_re_percentage = stats['std_dev_re_percentage']
        simulation_record.probability_75_percent = stats['probability_75_percent']
        simulation_record.probability_85_percent = stats['probability_85_percent']
        simulation_record.status = 'completed'
        simulation_record.save()

        # Update target scenario with probability result
        self.target_scenario.probability_percentage = stats['probability_85_percent']
        self.target_scenario.save(update_fields=['probability_percentage'])

        # Create histogram
        hist, bin_edges = np.histogram(re_percentage_results, bins=50)
        histogram_data = {
            'bins': bin_edges.tolist(),
            'counts': hist.tolist(),
        }

        # Store detailed results
        MonteCarloResult.objects.create(
            simulation=simulation_record,
            re_percentage_distribution=histogram_data,
            percentiles=stats['percentiles'],
            sample_iterations=re_percentage_results[:1000].tolist(),  # First 1000 for debugging
        )

        logger.info("Results stored successfully")

    def _store_parameters(self, simulation_record, category, value, description):
        """
        Store simulation parameters for auditing.

        Args:
            simulation_record: MonteCarloSimulation instance
            category: str, parameter category
            value: dict, parameter values
            description: str, parameter description
        """
        from siren_web.models import MonteCarloParameter

        for key, val in value.items():
            MonteCarloParameter.objects.create(
                simulation=simulation_record,
                parameter_category=category,
                parameter_name=key,
                parameter_value=val,
                description=description
            )

        logger.debug(f"Stored {len(value)} parameters for category '{category}'")