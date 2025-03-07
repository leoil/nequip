import math

import torch

import e3nn.o3
import e3nn.nn


# == Uniform init ==
def unit_uniform_init_(t: torch.Tensor):
    """Uniform initialization with <x_i^2> = 1"""
    t.uniform_(-math.sqrt(3), math.sqrt(3))


def uniform_initialize_fcs(mod: torch.nn.Module):
    """Initialize ``e3nn.nn.FullyConnectedNet``s with ``unit_uniform_init_``

    No need to do torch.nn.Linear, which is uniform by default.
    """
    if isinstance(mod, e3nn.nn.FullyConnectedNet):
        for layer in mod:
            unit_uniform_init_(layer.weight)


def uniform_initialize_equivariant_linears(mod: torch.nn.Module):
    """Initialize ``e3nn.o3.Linear``s that have internal weights with ``unit_uniform_init_``"""
    if isinstance(mod, e3nn.o3.Linear) and mod.internal_weights:
        unit_uniform_init_(mod.weight)


def uniform_initialize_tp_internal_weights(mod: torch.nn.Module):
    """Initialize ``e3nn.o3.TensorProduct``s that have internal weights with ``unit_uniform_init_``"""
    if isinstance(mod, e3nn.o3.TensorProduct) and mod.internal_weights:
        unit_uniform_init_(mod.weight)


# == Xavier ==
def xavier_initialize_fcs(mod: torch.nn.Module):
    """Initialize ``e3nn.nn.FullyConnectedNet``s and ``torch.nn.Linear``s with Xavier uniform initialization"""
    if isinstance(mod, e3nn.nn.FullyConnectedNet):
        for layer in mod:
            # in FC:
            # h_in, _h_out = W.shape
            # W = W / h_in**0.5
            torch.nn.init.xavier_uniform_(
                layer.weight, gain=layer.weight.shape[0] ** 0.5
            )
    elif isinstance(mod, torch.nn.Linear):
        torch.nn.init.xavier_uniform_(mod.weight)


# == Orthogonal ==
# TODO: does this normalization make any sense
def unit_orthogonal_init_(t: torch.Tensor):
    """Orthogonal init with <x_i^2> = 1"""
    assert t.ndim == 2
    torch.nn.init.orthogonal_(t, gain=math.sqrt(max(t.shape)))


def unit_orthogonal_initialize_equivariant_linears(mod: torch.nn.Module):
    """Initialize ``e3nn.o3.Linear``s that have internal weights with ``unit_orthogonal_init_``"""
    if isinstance(mod, e3nn.o3.Linear) and mod.internal_weights:
        for w in mod.weight_views():
            unit_orthogonal_init_(w)


def unit_orthogonal_initialize_fcs(mod: torch.nn.Module):
    """Initialize ``e3nn.nn.FullyConnectedNet``s and ``torch.nn.Linear``s with ``unit_orthogonal_init_``"""
    if isinstance(mod, e3nn.nn.FullyConnectedNet):
        for layer in mod:
            unit_orthogonal_init_(layer.weight)
    elif isinstance(mod, torch.nn.Linear):
        unit_orthogonal_init_(mod.weight)


def unit_orthogonal_initialize_e3nn_fcs(mod: torch.nn.Module):
    """Initialize only ``e3nn.nn.FullyConnectedNet``s with ``unit_orthogonal_init_``"""
    if isinstance(mod, e3nn.nn.FullyConnectedNet):
        for layer in mod:
            unit_orthogonal_init_(layer.weight)


def orthogonal_initialize_equivariant_linears(mod: torch.nn.Module):
    """Initialize ``e3nn.o3.Linear``s that have internal weights with ``torch.nn.init.orthogonal_``"""
    if isinstance(mod, e3nn.o3.Linear) and mod.internal_weights:
        for w in mod.weight_views():
            torch.nn.init.orthogonal_(w)


def orthogonal_initialize_fcs(mod: torch.nn.Module):
    """Initialize ``e3nn.nn.FullyConnectedNet``s and ``torch.nn.Linear``s with ``torch.nn.init.orthogonal_``"""
    if isinstance(mod, e3nn.nn.FullyConnectedNet):
        for layer in mod:
            torch.nn.init.orthogonal_(layer.weight)
    elif isinstance(mod, torch.nn.Linear):
        torch.nn.init.orthogonal_(mod.weight)


def orthogonal_initialize_e3nn_fcs(mod: torch.nn.Module):
    """Initialize only ``e3nn.nn.FullyConnectedNet``s with ``torch.nn.init.orthogonal_``"""
    if isinstance(mod, e3nn.nn.FullyConnectedNet):
        for layer in mod:
            torch.nn.init.orthogonal_(layer.weight)
