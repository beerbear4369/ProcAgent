"""
ProMax-related data models.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class BlockType(str, Enum):
    """Supported ProMax block types."""
    AMINE_TREATER = "AmineTreater"
    SEPARATOR = "Separator"
    HEAT_EXCHANGER = "HeatExchanger"
    COMPRESSOR = "Compressor"
    PUMP = "Pump"
    VALVE = "Valve"
    MIXER = "Mixer"
    SPLITTER = "Splitter"


class BlockIdentification(BaseModel):
    """Result of block identification from PFD or chat."""

    block_type: BlockType
    block_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    description: Optional[str] = None

    # Source of identification
    from_pfd: bool = False
    from_chat: bool = False


class ComponentComposition(BaseModel):
    """Component composition for a stream."""

    components: Dict[str, float] = Field(
        description="Component name to mole fraction mapping"
    )

    @field_validator("components")
    @classmethod
    def validate_composition_sum(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Validate that mole fractions sum to 1.0 (within tolerance)."""
        if not v:
            return v
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Composition mole fractions must sum to 1.0, got {total:.4f}"
            )
        return v


class StreamProperties(BaseModel):
    """Physical properties of a process stream."""

    temperature_c: Optional[float] = Field(
        default=None,
        ge=-273.15,
        le=1000.0,
        description="Temperature in Celsius"
    )
    pressure_kpa: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Pressure in kPa (absolute)"
    )
    molar_flow_kmol_hr: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Molar flow rate in kmol/hr"
    )
    mass_flow_kg_hr: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Mass flow rate in kg/hr"
    )


class StreamSpec(BaseModel):
    """Complete specification for a process stream."""

    name: str
    stream_type: str = "inlet"  # inlet, outlet
    properties: StreamProperties = Field(default_factory=StreamProperties)
    composition: Optional[ComponentComposition] = None

    # Position for Visio shape (inches)
    x_position: Optional[float] = None
    y_position: Optional[float] = None


class PerformanceTarget(BaseModel):
    """Performance target for simulation comparison."""

    parameter: str  # e.g., "Offgas H2S", "Rich Amine Loading"
    target_value: float
    unit: str
    comparison: str = "le"  # le, ge, eq (less/equal, greater/equal, equal)
    tolerance: float = 0.0  # Allowed deviation for 'eq' comparison


class SimulationStatus(str, Enum):
    """Status of a simulation run."""
    PENDING = "pending"
    RUNNING = "running"
    CONVERGED = "converged"
    NOT_CONVERGED = "not_converged"
    ERROR = "error"


class SimulationResult(BaseModel):
    """Results from a simulation run."""

    status: SimulationStatus
    solver_status_code: Optional[int] = None
    error_message: Optional[str] = None

    # Output stream results
    stream_results: Dict[str, StreamProperties] = Field(default_factory=dict)

    # Specific result values for target comparison
    result_values: Dict[str, float] = Field(
        default_factory=dict,
        description="Parameter name to value mapping"
    )


class TargetAssessment(BaseModel):
    """Assessment of a single performance target."""

    target: PerformanceTarget
    actual_value: float
    passed: bool
    deviation: float  # Actual - Target
    deviation_percent: Optional[float] = None


class ResultsComparison(BaseModel):
    """Comparison of simulation results against targets."""

    assessments: List[TargetAssessment]
    overall_pass: bool
    summary: str


class AdjustmentSuggestion(BaseModel):
    """Suggested parameter adjustment to improve results."""

    parameter: str
    current_value: float
    suggested_value: float
    unit: str
    rationale: str
    expected_impact: str
