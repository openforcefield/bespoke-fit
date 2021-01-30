from enum import Enum
from typing import Any, Dict, List, Optional

from simtk import unit

from openff.bespokefit.common_structures import SchemaBase, Status
from openff.qcsubmit.results import SingleResult


class CollectionMethod(str, Enum):

    TorsionDrive1D = "torsiondrive1d"  # qcsubmit torsiondrives
    TorsionDrive2D = "torsiondrive2d"
    Optimization = "optimization"  # qcsubmit optimization
    Hessian = "hessian"  # qcsubmit hessian
    Energy = "energy"  # qcsubmit collection of single points
    Gradient = "gradient"
    Local = "local"  # a non qcsubmit function which should be executed locally


class Precedence(str, Enum):

    Serial = "serial"
    Parallel = "parallel"


class WorkflowStage(SchemaBase):
    """
    Here we detail a stage in a reference data collection workflow.
    """

    method: CollectionMethod
    result: Optional[List[SingleResult]] = None
    status: Status = Status.Prepared
    keywords: Dict[str, Any] = {}
    precedence: Precedence = Precedence.Serial
    retires: int = 0
    job_id: str = ""

    _enum_fields = ["precedence", "status", "method"]

    def get_result_geometries(self) -> List[unit.Quantity]:
        """
        For each result in the workflow stage extract the geometries useful for hessian workflows.
        """
        geometries = []
        for result in self.result:
            new_geometry = unit.Quantity(result.molecule.geometry, unit.bohr)
            geometries.append(new_geometry)

        return geometries


# make some pre defined workflows
OptimizationWorkflow = [
    WorkflowStage(method=CollectionMethod.Optimization, precedence=Precedence.Serial)
]

TorsiondriveWorkflow = [
    WorkflowStage(method=CollectionMethod.TorsionDrive1D, precedence=Precedence.Serial)
]

HessianWorkflow = [
    WorkflowStage(method=CollectionMethod.Optimization, precedence=Precedence.Serial),
    WorkflowStage(method=CollectionMethod.Hessian, precedence=Precedence.Serial),
]

RespWorkflow = [
    WorkflowStage(method=CollectionMethod.Optimization, precedence=Precedence.Serial),
    WorkflowStage(method=CollectionMethod.Energy, precedence=Precedence.Serial),
    WorkflowStage(method=CollectionMethod.Local, precedence=Precedence.Serial),
]
