from copy import deepcopy
from typing import Union, Sequence, Tuple

import torch

from nequip.data import AtomicDataDict
from torch_runstats import RunningStats, Reduction

from ._loss import find_loss_function
from ._key import ABBREV

metrics_to_reduction = {"mae": Reduction.MEAN, "rmse": Reduction.RMS}


class Metrics:
    """Computes all mae, rmse needed for report

    Args:
        components: a list or a tuples of definition.

    Example:

    ```
    components = [(key1, "rmse"), (key2, "mse)]
    ```

    You can also offer more details with a dictionary. The keys can be any keys for RunningStats or

    report_per_component (bool): if True, report the mean on each component (equivalent to mean(axis=0) in numpy),
                                 otherwise, take the mean across batch and all components for vector data.
    functional: the function to compute the error. It has to be exactly the same as the one defined in torch.nn.
                default: "L1Loss"
    PerSpecies: whether compute the estimation for each species or not


    ```
    components = (
        (
            AtomicDataDict.FORCE_KEY,
            "rmse",
            {"PerSpecies": True, "functional": "L1Loss", "dim": 3},
        ),
        (AtomicDataDict.FORCE_KEY, "mae", {"dim": 3}),
    )
    ```

    """

    def __init__(
        self, components: Sequence[Union[Tuple[str, str], Tuple[str, str, dict]]]
    ):

        self.running_stats = {}
        self.per_species = {}
        self.funcs = {}
        self.kwargs = {}
        for component in components:

            key, reduction, params = Metrics.parse(component)

            functional = params.pop("functional", "L1Loss")

            # default is to flatten the array
            per_species = params.pop("PerSpecies", False)

            if key not in self.running_stats:
                self.running_stats[key] = {}
                self.per_species[key] = {}
                self.funcs[key] = find_loss_function(functional, {})
                self.kwargs[key] = {}

            # store for initialization
            kwargs = deepcopy(params)

            # by default, report a scalar that is mae and rmse over all component
            self.kwargs[key][reduction] = dict(
                reduction=metrics_to_reduction.get(reduction, reduction),
            )
            self.kwargs[key][reduction].update(kwargs)

            self.per_species[key][reduction] = per_species

    def init_runstat(self, params, error: torch.Tensor):

        kwargs = deepcopy(params)
        if "dim" not in kwargs:
            kwargs["dim"] = error.shape[1:]

        if "reduce_dims" not in kwargs:
            if not kwargs.pop("report_per_component", False):
                kwargs["reduce_dims"] = tuple(range(len(error.shape) - 1))

        rs = RunningStats(**kwargs)
        rs.to(device=error.device)
        return rs

    @staticmethod
    def parse(component):
        # parse the input list
        reduction = "mae"
        params = {}

        if isinstance(component, str):
            key = component
        elif len(component) == 1:
            key = component[0]
        elif len(component) == 2:
            key, reduction = component
        elif len(component) == 3:
            key, reduction, _params = component
            params = {k: deepcopy(v) for k, v in _params.items()}
        else:
            raise ValueError(
                f"tuple should have a max length of 3 but {len(component)} is given"
            )
        return key, reduction, params

    def __call__(self, pred: dict, ref: dict):

        metrics = {}
        for key, func in self.funcs.items():
            error = func(
                pred=pred,
                ref=ref,
                key=key,
                atomic_weight_on=False,
                mean=False,
            )

            for reduction, kwargs in self.kwargs[key].items():

                # initialize the internal run_stat base on the error shape
                if reduction not in self.running_stats[key]:
                    self.running_stats[key][reduction] = self.init_runstat(
                        params=kwargs, error=error
                    )

                stat = self.running_stats[key][reduction]

                params = {}
                if self.per_species[key][reduction]:
                    # TO DO, this needs OneHot component. will need to be decoupled
                    params = {"accumulate_by": pred[AtomicDataDict.SPECIES_INDEX_KEY]}

                if stat.dim == () and not self.per_species[key][reduction]:
                    metrics[(key, reduction)] = stat.accumulate_batch(
                        error.flatten(), **params
                    )
                else:
                    metrics[(key, reduction)] = stat.accumulate_batch(error, **params)

        return metrics

    def reset(self):
        for stats in self.running_stats.values():
            for stat in stats.values():
                stat.reset()

    def to(self, device):
        for stats in self.running_stats.values():
            for stat in stats.values():
                stat.to(device=device)

    def current_result(self):

        metrics = {}
        for key, stats in self.running_stats.items():
            for reduction, stat in stats.items():
                metrics[(key, reduction)] = stat.current_result()
        return metrics

    def flatten_metrics(self, metrics, allowed_species=None):

        flat_dict = {}
        skip_keys = []
        for k, value in metrics.items():

            key, reduction = k
            short_name = ABBREV.get(key, key)

            item_name = f"{short_name}_{reduction}"

            stat = self.running_stats[key][reduction]
            per_species = self.per_species[key][reduction]

            if per_species:

                element_names = (
                    list(range(value.shape[0]))
                    if allowed_species is None
                    else list(allowed_species)
                )

                if stat.output_dim == tuple():
                    for id_ele, v in enumerate(value):
                        flat_dict[f"{element_names[id_ele]}_{item_name}"] = v.item()

                    flat_dict[f"all_{item_name}"] = value.mean().item()
                else:
                    for id_ele, vec in enumerate(value):
                        ele = element_names[id_ele]
                        for idx, v in enumerate(vec):
                            name = f"{ele}_{item_name}_{idx}"
                            flat_dict[name] = v.item()
                            skip_keys.append(name)

            else:
                if stat.output_dim == tuple():
                    # a scalar
                    flat_dict[item_name] = value.item()
                else:
                    # a vector
                    for idx, v in enumerate(value.flatten()):
                        flat_dict[f"{item_name}_{idx}"] = v.item()
        return flat_dict, skip_keys
