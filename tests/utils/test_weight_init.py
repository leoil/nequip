import pytest

import torch

from nequip.utils.initialization import unit_uniform_init_, unit_orthogonal_init_


@pytest.mark.parametrize("init_func_", [unit_uniform_init_, unit_orthogonal_init_])
def test_2mom(init_func_):
    t = torch.empty(1000, 100)
    init_func_(t)
    assert (t.square().mean() - 1.0).abs() <= 0.1
