from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class PipelineConfig:
    api_base: str = "https://api.worldquantbrain.com"
    
    # In-Sample Performance Thresholds
    min_sharpe: float = 1.25
    min_fitness: float = 1.00
    min_turnover: float = 0.01
    max_turnover: float = 0.70
    max_self_correlation: float = 0.70
    require_all_checks_pass: bool = True
    
    # Default Simulation Settings
    default_instrument_type: str = "EQUITY"
    default_region: str = "USA"
    default_universe: str = "TOP3000"
    default_delay: int = 1
    default_decay: int = 10
    default_neutralization: str = "SUBINDUSTRY"
    default_truncation: float = 0.08
    default_pasteurization: str = "ON"
    default_unit_handling: str = "VERIFY"
    default_nan_handling: str = "OFF"
    default_language: str = "FASTEXPR"
    
    # Execution & Rate Limits
    poll_interval: float = 3.0
    simulation_timeout: int = 300
    check_timeout: int = 60
    max_concurrent_simulations: int = 3
    db_path: str = "alphas_audit.db"
    
    # Safety Rule: strictly prevent automated alpha submission
    auto_submit: bool = False

