"""
Shared utilities for generation data plotting views.

This module consolidates common functionality used by both facility_scada_views.py
and supplyfactors_views.py to reduce code duplication.
"""

import math
from datetime import datetime
from typing import Optional


def get_hour_range_from_months(start_month: int, end_month: int) -> tuple[int, int]:
    """Convert month numbers to hour ranges (1-based months and hours).

    Args:
        start_month: Start month (1-12)
        end_month: End month (1-12)

    Returns:
        Tuple of (start_hour, end_hour) for a non-leap year (1-8760)
    """
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    start_hour = sum(days_per_month[:start_month-1]) * 24 + 1
    end_hour = sum(days_per_month[:end_month]) * 24
    return start_hour, end_hour


def get_hour_of_year(dt: datetime) -> int:
    """Calculate hour of year from datetime (1-based).

    Args:
        dt: Datetime to convert

    Returns:
        Hour of year (1-8760 for non-leap year, 1-8784 for leap year)
    """
    start_of_year = datetime(dt.year, 1, 1, tzinfo=dt.tzinfo)
    delta = dt - start_of_year
    return int(delta.total_seconds() / 3600) + 1


def get_month_from_hour(hour: int) -> int:
    """Determine which month a given hour of year belongs to.

    Args:
        hour: Hour of year (1-based)

    Returns:
        Month number (1-12)
    """
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    cumulative_hours = [0]
    for days in days_per_month:
        cumulative_hours.append(cumulative_hours[-1] + days * 24)

    for i in range(12):
        if hour <= cumulative_hours[i + 1]:
            return i + 1
    return 12


def get_week_from_hour(hour: int) -> int:
    """Determine which week a given hour of year belongs to.

    Args:
        hour: Hour of year (1-based)

    Returns:
        Week number (1-52)
    """
    return ((hour - 1) // 168) + 1


def aggregate_by_hour(hour_data: list[dict], value_field: str = 'quantity') -> dict:
    """Aggregate data by hour (handles duplicates by averaging).

    Args:
        hour_data: List of dicts with 'hour' and value field(s)
        value_field: Name of the value field to aggregate

    Returns:
        Dict with 'periods' and value field lists
    """
    hour_dict = {}
    for entry in hour_data:
        hour = entry['hour']
        value = entry.get(value_field, 0) or 0
        if hour not in hour_dict:
            hour_dict[hour] = []
        hour_dict[hour].append(value)

    hours = sorted(hour_dict.keys())
    values = [sum(hour_dict[h]) / len(hour_dict[h]) for h in hours]

    return {
        'periods': hours,
        value_field: values
    }


def aggregate_by_week(hour_data: list[dict], value_field: str = 'quantity') -> dict:
    """Aggregate data by week (168 hours per week).

    Args:
        hour_data: List of dicts with 'hour' and value field(s)
        value_field: Name of the value field to aggregate

    Returns:
        Dict with 'periods' (week numbers) and averaged values
    """
    week_dict = {}

    for entry in hour_data:
        hour = entry['hour']
        value = entry.get(value_field, 0) or 0
        week = get_week_from_hour(hour)

        if week not in week_dict:
            week_dict[week] = []
        week_dict[week].append(value)

    weeks = sorted(week_dict.keys())
    values = [sum(week_dict[w]) / len(week_dict[w]) for w in weeks]

    return {
        'periods': weeks,
        value_field: values
    }


def aggregate_by_month(hour_data: list[dict], value_field: str = 'quantity') -> dict:
    """Aggregate data by month.

    Args:
        hour_data: List of dicts with 'hour' and value field(s)
        value_field: Name of the value field to aggregate

    Returns:
        Dict with 'periods' (month numbers 1-12) and averaged values
    """
    month_dict = {}

    for entry in hour_data:
        hour = entry['hour']
        value = entry.get(value_field, 0) or 0
        month = get_month_from_hour(hour)

        if month not in month_dict:
            month_dict[month] = []
        month_dict[month].append(value)

    months = sorted(month_dict.keys())
    values = [sum(month_dict[m]) / len(month_dict[m]) for m in months]

    return {
        'periods': months,
        value_field: values
    }


def aggregate_by_period(hour_data: list[dict], period: str, value_field: str = 'quantity') -> dict:
    """Generic aggregation function that dispatches to hour/week/month.

    Args:
        hour_data: List of dicts with 'hour' and value field(s)
        period: 'hour', 'week', or 'month'
        value_field: Name of the value field to aggregate

    Returns:
        Dict with 'periods' and aggregated values

    Raises:
        ValueError: If period is not 'hour', 'week', or 'month'
    """
    if period == 'hour':
        return aggregate_by_hour(hour_data, value_field)
    elif period == 'week':
        return aggregate_by_week(hour_data, value_field)
    elif period == 'month':
        return aggregate_by_month(hour_data, value_field)
    else:
        raise ValueError(f"Invalid period: {period}. Must be 'hour', 'week', or 'month'")


def aggregate_multiple_fields(hour_data: list[dict], period: str, value_fields: list[str]) -> dict:
    """Aggregate multiple value fields by period.

    Args:
        hour_data: List of dicts with 'hour' and value field(s)
        period: 'hour', 'week', or 'month'
        value_fields: List of field names to aggregate

    Returns:
        Dict with 'periods' and aggregated values for each field
    """
    if period == 'hour':
        get_period = lambda h: h
    elif period == 'week':
        get_period = get_week_from_hour
    elif period == 'month':
        get_period = get_month_from_hour
    else:
        raise ValueError(f"Invalid period: {period}")

    # Initialize period dictionaries for each field
    period_data = {}

    for entry in hour_data:
        hour = entry['hour']
        p = get_period(hour)

        if p not in period_data:
            period_data[p] = {field: [] for field in value_fields}

        for field in value_fields:
            value = entry.get(field, 0) or 0
            period_data[p][field].append(value)

    periods = sorted(period_data.keys())
    result = {'periods': periods}

    for field in value_fields:
        result[field] = [
            sum(period_data[p][field]) / len(period_data[p][field])
            for p in periods
        ]

    return result


def calculate_correlation_metrics(data1: list, data2: list,
                                   pad_arrays: bool = True) -> Optional[dict]:
    """Calculate correlation and complementarity metrics between two datasets.

    Args:
        data1: First value array
        data2: Second value array
        pad_arrays: If True, pad shorter array with zeros. If False, return None
                   for mismatched lengths.

    Returns:
        Dict with correlation metrics, or None if arrays can't be compared
    """
    if len(data1) != len(data2):
        if pad_arrays:
            max_len = max(len(data1), len(data2))
            data1 = list(data1) + [0] * (max_len - len(data1))
            data2 = list(data2) + [0] * (max_len - len(data2))
        else:
            return None

    n = len(data1)
    if n == 0:
        return None

    # Calculate means
    mean1 = sum(data1) / n
    mean2 = sum(data2) / n

    # Calculate variances and standard deviations
    variance1 = sum((x - mean1) ** 2 for x in data1) / n
    variance2 = sum((x - mean2) ** 2 for x in data2) / n
    std1 = math.sqrt(variance1)
    std2 = math.sqrt(variance2)

    # Calculate Pearson correlation coefficient
    if std1 == 0 or std2 == 0:
        correlation = 0
    else:
        covariance = sum((data1[i] - mean1) * (data2[i] - mean2) for i in range(n)) / n
        correlation = covariance / (std1 * std2)

    # Calculate complementarity score (inverse of absolute correlation)
    complementarity_score = 1 - abs(correlation)

    # Calculate percentage of complementary periods (one high when other is low)
    complementary_periods = 0
    for i in range(n):
        if (data1[i] > mean1 and data2[i] < mean2) or (data1[i] < mean1 and data2[i] > mean2):
            complementary_periods += 1
    complementary_pct = (complementary_periods / n) * 100

    # Calculate combined variability reduction
    combined = [(data1[i] + data2[i]) / 2 for i in range(n)]
    combined_mean = sum(combined) / n
    var_combined = sum((combined[i] - combined_mean) ** 2 for i in range(n)) / n

    avg_var = (variance1 + variance2) / 2
    if avg_var > 0:
        variability_reduction = ((avg_var - var_combined) / avg_var) * 100
    else:
        variability_reduction = 0

    # Calculate coefficients of variation
    cv1 = (std1 / mean1 * 100) if mean1 > 0 else 0
    cv2 = (std2 / mean2 * 100) if mean2 > 0 else 0
    combined_std = math.sqrt(var_combined)
    cv_combined = (combined_std / combined_mean * 100) if combined_mean > 0 else 0

    return {
        'correlation': round(correlation, 4),
        'complementarity_score': round(complementarity_score, 4),
        'complementary_periods_pct': round(complementary_pct, 2),
        'variability_reduction': round(variability_reduction, 2),
        'cv_data1': round(cv1, 2),
        'cv_data2': round(cv2, 2),
        'cv_combined': round(cv_combined, 2),
        'interpretation': interpret_correlation(correlation, complementarity_score, variability_reduction)
    }


def interpret_correlation(correlation: float, complementarity: float,
                          variability_reduction: float) -> str:
    """Provide human-readable interpretation of correlation metrics for SCADA vs Simulated comparison.

    Args:
        correlation: Pearson correlation coefficient (-1 to 1)
        complementarity: Complementarity score (0 to 1) - not used for SCADA comparison
        variability_reduction: Percentage variability reduction - not used for SCADA comparison

    Returns:
        Human-readable interpretation string focused on simulation accuracy
    """
    # For SCADA vs Simulated comparison, focus on how well simulation tracks actual generation
    if correlation >= 0.95:
        return "Excellent - Simulation closely tracks actual SCADA generation patterns"
    elif correlation >= 0.9:
        return "Very good - Simulation captures most variation in actual generation"
    elif correlation >= 0.8:
        return "Good - Simulation generally follows actual generation trends"
    elif correlation >= 0.7:
        return "Moderate - Simulation captures overall trends but misses some variations"
    elif correlation >= 0.5:
        return "Fair - Simulation only partially captures actual generation patterns. Consider reviewing resource data or model parameters"
    elif correlation >= 0.3:
        return "Weak - Significant differences between simulated and actual generation. May indicate curtailment, outages, or model issues"
    else:
        return "Poor - Simulation does not match actual generation. Check for data issues, curtailment periods, or incorrect facility mapping"


def calculate_error_metrics(actual: list, predicted: list) -> Optional[dict]:
    """Calculate forecast error metrics.

    Args:
        actual: Actual/observed values (e.g., SCADA data)
        predicted: Predicted/simulated values (e.g., SupplyFactors data)

    Returns:
        Dict with error metrics, or None if arrays are mismatched
    """
    if len(actual) != len(predicted):
        return None

    n = len(actual)
    if n == 0:
        return None

    # Mean Absolute Error
    mae = sum(abs(actual[i] - predicted[i]) for i in range(n)) / n

    # Mean Squared Error and Root Mean Squared Error
    mse = sum((actual[i] - predicted[i]) ** 2 for i in range(n)) / n
    rmse = math.sqrt(mse)

    # Mean Bias Error (positive = overestimate, negative = underestimate)
    mbe = sum(predicted[i] - actual[i] for i in range(n)) / n

    # Mean Absolute Percentage Error (avoid division by zero)
    mape_sum = 0
    mape_count = 0
    for i in range(n):
        if actual[i] != 0:
            mape_sum += abs((actual[i] - predicted[i]) / actual[i])
            mape_count += 1
    mape = (mape_sum / mape_count * 100) if mape_count > 0 else None

    # Normalized RMSE (as percentage of mean actual)
    mean_actual = sum(actual) / n
    nrmse = (rmse / mean_actual * 100) if mean_actual > 0 else None

    return {
        'mae': round(mae, 3),
        'rmse': round(rmse, 3),
        'mbe': round(mbe, 3),
        'mape': round(mape, 2) if mape is not None else None,
        'nrmse': round(nrmse, 2) if nrmse is not None else None,
        'interpretation': interpret_error_metrics(mae, rmse, mbe, mean_actual)
    }


def interpret_error_metrics(mae: float, rmse: float, mbe: float,
                            mean_actual: float) -> str:
    """Provide human-readable interpretation of error metrics.

    Args:
        mae: Mean Absolute Error
        rmse: Root Mean Squared Error
        mbe: Mean Bias Error
        mean_actual: Mean of actual values (for context)

    Returns:
        Human-readable interpretation string
    """
    interpretation = []

    # Bias interpretation
    if mean_actual > 0:
        bias_pct = (mbe / mean_actual) * 100
        if bias_pct > 5:
            interpretation.append(f"Simulated values overestimate actual by {bias_pct:.1f}% on average")
        elif bias_pct < -5:
            interpretation.append(f"Simulated values underestimate actual by {abs(bias_pct):.1f}% on average")
        else:
            interpretation.append("Simulated values are well-calibrated with minimal bias")

    # Error magnitude interpretation
    if mean_actual > 0:
        mae_pct = (mae / mean_actual) * 100
        if mae_pct < 10:
            interpretation.append(f"Low average error ({mae_pct:.1f}% of mean)")
        elif mae_pct < 25:
            interpretation.append(f"Moderate average error ({mae_pct:.1f}% of mean)")
        else:
            interpretation.append(f"High average error ({mae_pct:.1f}% of mean)")

    return " | ".join(interpretation) if interpretation else "Unable to interpret metrics"


def get_x_label(aggregation: str) -> str:
    """Get the appropriate x-axis label for an aggregation level.

    Args:
        aggregation: 'hour', 'week', or 'month'

    Returns:
        Human-readable x-axis label
    """
    labels = {
        'hour': 'Hour of Year',
        'week': 'Week of Year',
        'month': 'Month of Year'
    }
    return labels.get(aggregation, 'Period')


def get_hour_of_day(hour_of_year: int) -> int:
    """Get the hour of day (0-23) from hour of year.

    Args:
        hour_of_year: Hour of year (1-based, 1-8760)

    Returns:
        Hour of day (0-23)
    """
    return (hour_of_year - 1) % 24


def is_peak_hour(hour_of_year: int, peak_start: int = 16, peak_end: int = 21) -> bool:
    """Check if an hour of year falls within peak demand hours.

    Peak hours are typically late afternoon/evening when demand is highest
    and curtailment is least likely for renewable generation.

    Default peak hours are 4pm-9pm (16:00-21:00) for SWIS/WEM.

    Args:
        hour_of_year: Hour of year (1-based, 1-8760)
        peak_start: Start of peak period (hour of day, 0-23). Default 16 (4pm).
        peak_end: End of peak period (hour of day, 0-23). Default 21 (9pm).

    Returns:
        True if the hour falls within peak hours
    """
    hour_of_day = get_hour_of_day(hour_of_year)
    return peak_start <= hour_of_day < peak_end


def filter_to_peak_hours(hours: list, values: list,
                          peak_start: int = 16, peak_end: int = 21) -> tuple[list, list]:
    """Filter hour/value pairs to only include peak hours.

    Args:
        hours: List of hours of year (1-based)
        values: List of corresponding values
        peak_start: Start of peak period (hour of day, 0-23). Default 16 (4pm).
        peak_end: End of peak period (hour of day, 0-23). Default 21 (9pm).

    Returns:
        Tuple of (filtered_hours, filtered_values)
    """
    filtered_hours = []
    filtered_values = []

    for hour, value in zip(hours, values):
        if is_peak_hour(hour, peak_start, peak_end):
            filtered_hours.append(hour)
            filtered_values.append(value)

    return filtered_hours, filtered_values


# Peak hour presets for SWIS (Western Australia)
PEAK_HOUR_PRESETS = {
    'all': {'start': 0, 'end': 24, 'label': 'All Hours'},
    'peak': {'start': 16, 'end': 21, 'label': 'Peak (4pm-9pm)'},
    'shoulder': {'start': 7, 'end': 16, 'label': 'Shoulder (7am-4pm)'},
    'off_peak': {'start': 21, 'end': 7, 'label': 'Off-Peak (9pm-7am)'},
    'daytime': {'start': 6, 'end': 20, 'label': 'Daytime (6am-8pm)'},
    'solar_peak': {'start': 10, 'end': 15, 'label': 'Solar Peak (10am-3pm)'},
}
