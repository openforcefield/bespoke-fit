"""
Tools for dealing with forcefield manipulation.
"""

from typing import Dict, Iterable, List, Tuple, Union

from openforcefield import topology as off
from openforcefield.typing.engines.smirnoff import (
    AngleHandler,
    BondHandler,
    ForceField,
    ProperTorsionHandler,
    vdWHandler,
)

from .common_structures import SmirksType
from .schema.smirks import AngleSmirks, AtomSmirks, BondSmirks, TorsionSmirks
from .utils import smirks_from_off


class ForceFieldEditor:
    def __init__(self, forcefield_name: str):
        """
        Gather the forcefield ready for manipulation.

        Parameters
        ----------
        forcefield_name: str
            The string of the target forcefield path.

        Notes
        ------
            This will always try to strip the constraints parameter handler as the FF should be unconstrained for fitting.
        """
        self.forcefield = ForceField(forcefield_name, allow_cosmetic_attributes=True)

        # try and strip a constraint handler
        try:
            del self.forcefield._parameter_handlers["Constraints"]
        except KeyError:
            pass

    def add_smirks(
        self,
        smirks: List[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]],
        parameterize: bool = True,
    ) -> None:
        """
        Work out which type of smirks this is and add it to the forcefield, if this is not a bespoke parameter update the value in the forcefield.
        """

        _smirks_conversion = {
            SmirksType.Bonds: BondHandler.BondType,
            SmirksType.Angles: AngleHandler.AngleType,
            SmirksType.ProperTorsions: ProperTorsionHandler.ProperTorsionType,
            SmirksType.Vdw: vdWHandler.vdWType,
        }
        _smirks_ids = {
            SmirksType.Bonds.value: "b",
            SmirksType.Angles.value: "a",
            SmirksType.ProperTorsions.value: "t",
            SmirksType.Vdw.value: "n",
        }
        new_params = {}
        for smirk in smirks:
            if smirk.type.value not in new_params:
                new_params[smirk.type.value] = [
                    smirk,
                ]
            else:
                if smirk not in new_params[smirk.type.value]:
                    new_params[smirk.type.value].append(smirk)

        for smirk_type, parameters in new_params.items():
            current_params = self.forcefield.get_parameter_handler(
                smirk_type
            ).parameters
            no_params = len(current_params)
            for i, parameter in enumerate(parameters, start=2):
                smirk_data = parameter.to_off_smirks()
                if not parameterize:
                    del smirk_data["parameterize"]
                # check if the parameter is new
                try:
                    current_param = current_params[parameter.smirks]
                    smirk_data["id"] = current_param.id
                    # update the parameter using the init to get around conditional assigment
                    current_param.__init__(**smirk_data)
                except KeyError:
                    smirk_data["id"] = _smirks_ids[smirk_type] + str(no_params + i)
                    current_params.append(_smirks_conversion[smirk_type](**smirk_data))

    def label_molecule(self, molecule: off.Molecule) -> Dict[str, str]:
        """
        Type the molecule with the forcefield and return a molecule parameter dictionary.

        Parameters
        ----------
        molecule: off.Molecule
            The openforcefield.topology.Molecule that should be labeled by the forcefield.

        Returns
        -------
        Dict[str, str]
            A dictionary of each parameter assigned to molecule organised by parameter handler type.
        """
        return self.forcefield.label_molecules(molecule.to_topology())[0]

    def get_smirks_parameters(
        self, molecule: off.Molecule, atoms: List[Tuple[int, ...]]
    ) -> List[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]]:
        """
        For a given molecule label it and get back the smirks patterns and parameters for the requested atoms.
        """
        _atoms_to_params = {
            1: SmirksType.Vdw,
            2: SmirksType.Bonds,
            3: SmirksType.Angles,
            4: SmirksType.ProperTorsions,
        }
        smirks = []
        labels = self.label_molecule(molecule=molecule)
        for atom_ids in atoms:
            # work out the parameter type from the length of the tuple
            smirk_class = _atoms_to_params[len(atom_ids)]
            # now we can get the handler type using the smirk type
            off_param = labels[smirk_class.value][atom_ids]
            smirk = smirks_from_off(off_smirks=off_param)
            smirk.atoms.add(atom_ids)
            if smirk not in smirks:
                smirks.append(smirk)
            else:
                # update the covered atoms
                index = smirks.index(smirk)
                smirks[index].atoms.add(atom_ids)
        return smirks

    def update_smirks_parameters(
        self,
        smirks: Iterable[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]],
    ) -> None:
        """
        Take a list of input smirks parameters and update the values of the parameters using the given forcefield in place.

        Parameters
        ----------
        smirks : Iterable[Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]]
            An iterable containing smirks schemas that are to be updated.

        """

        for smirk in smirks:
            new_parameter = self.forcefield.get_parameter_handler(
                smirk.type.value
            ).parameters[smirk.smirks]
            # now we just need to update the smirks with the new values
            smirk.update_parameters(off_smirk=new_parameter)

    def get_initial_parameters(
        self,
        molecule: off.Molecule,
        smirk: Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks],
        clear_existing: bool = True,
    ) -> Union[AtomSmirks, AngleSmirks, BondSmirks, TorsionSmirks]:
        """
        Find the initial parameters assigned to the atoms in the given smirks pattern and update the values to match the forcefield.
        """
        labels = self.label_molecule(molecule=molecule)
        # now find the atoms
        parameters = labels[smirk.type.value]
        openff_params = []
        for atoms in smirk.atoms:
            param = parameters[atoms]
            openff_params.append(param)

        # now check if they are different types
        types = set([param.id for param in openff_params])
        assert (
            len(types) == 1
        ), "The new smirks types have clustered some torsions that orginally had seperate parameters set initial value to None."
        # now update the parameter
        smirk.update_parameters(
            off_smirk=openff_params[0], clear_existing=clear_existing
        )
        return smirk
