import numpy as np
import pytest
import tempfile
import torch

from os.path import isdir

from ase.io import write

from nequip.data import (
    AtomicDataDict,
    AtomicInMemoryDataset,
    NpzDataset,
    ASEDataset,
)
from nequip.utils import dataset_from_config, Config


@pytest.fixture(scope="module")
def ase_file(molecules):
    with tempfile.NamedTemporaryFile(suffix=".xyz") as fp:
        for atoms in molecules:
            write(fp.name, atoms, format="extxyz", append=True)
        yield fp.name


@pytest.fixture(scope="session")
def npz():
    natoms = 3
    nframes = 4
    yield dict(
        positions=np.random.random((nframes, natoms, 3)),
        force=np.random.random((nframes, natoms, 3)),
        energy=np.random.random(nframes),
        Z=np.random.randint(1, 8, size=(nframes, natoms)),
    )


@pytest.fixture(scope="session")
def npz_data(npz):
    with tempfile.NamedTemporaryFile(suffix=".npz") as path:
        np.savez(path.name, **npz)
        yield path.name


@pytest.fixture(scope="session")
def npz_dataset(npz_data, temp_data):
    a = NpzDataset(
        file_name=npz_data,
        root=temp_data + "/test_dataset",
        extra_fixed_fields={"r_max": 3},
    )
    yield a


@pytest.fixture(scope="function")
def root():
    with tempfile.TemporaryDirectory(prefix="datasetroot") as path:
        yield path


class TestInit:
    def test_init(self):
        with pytest.raises(NotImplementedError) as excinfo:
            a = AtomicInMemoryDataset(root=None)
        assert str(excinfo.value) == ""

    def test_npz(self, npz_data, root):
        g = NpzDataset(file_name=npz_data, root=root, extra_fixed_fields={"r_max": 3.0})
        assert isdir(g.root)
        assert isdir(f"{g.root}/processed")

    def test_ase(self, ase_file, root):
        a = ASEDataset(
            file_name=ase_file,
            root=root,
            extra_fixed_fields={"r_max": 3.0},
            ase_args=dict(format="extxyz"),
        )
        assert isdir(a.root)
        assert isdir(f"{a.root}/processed")


class TestStatistics:
    @pytest.mark.xfail(
        reason="Current subset hack doesn't support statistics of non-per-node callable"
    )
    def test_callable(self, npz_dataset, npz):
        # Get componentwise statistics
        ((f_mean, f_std),) = npz_dataset.statistics(
            [lambda d: torch.flatten(d[AtomicDataDict.FORCE_KEY])]
        )
        n_ex, n_at, _ = npz["force"].shape
        f_raveled = npz["force"].reshape((n_ex * n_at * 3,))
        assert np.allclose(np.mean(f_raveled), f_mean)
        # By default we follow torch convention of defaulting to the unbiased std
        assert np.allclose(np.std(f_raveled, ddof=1), f_std)

    def test_statistics(self, npz_dataset, npz):

        (eng_mean, eng_std), (Z_unique, Z_count) = npz_dataset.statistics(
            [AtomicDataDict.TOTAL_ENERGY_KEY, AtomicDataDict.ATOMIC_NUMBERS_KEY]
        )

        eng = npz["energy"]
        assert np.allclose(eng_mean, np.mean(eng))
        # By default we follow torch convention of defaulting to the unbiased std
        assert np.allclose(eng_std, np.std(eng, ddof=1))

        if isinstance(Z_count, torch.Tensor):
            Z_count = Z_count.numpy()
            Z_unique = Z_unique.numpy()

        uniq, count = np.unique(npz["Z"].ravel(), return_counts=True)
        assert np.all(Z_unique == uniq)
        assert np.all(Z_count == count)

    def test_with_subset(self, npz_dataset, npz):

        dataset = npz_dataset.index_select([0])

        ((Z_unique, Z_count), (force_rms,)) = dataset.statistics(
            [AtomicDataDict.ATOMIC_NUMBERS_KEY, AtomicDataDict.FORCE_KEY],
            modes=["count", "rms"],
        )
        print("npz", npz["Z"])

        uniq, count = np.unique(npz["Z"][0].ravel(), return_counts=True)
        assert np.all(Z_unique.numpy() == uniq)
        assert np.all(Z_count.numpy() == count)

        assert np.allclose(
            force_rms.numpy(), np.sqrt(np.mean(np.square(npz["force"][0])))
        )


class TestReload:
    @pytest.mark.parametrize("change_rmax", [0, 1])
    def test_reload(self, npz_dataset, npz_data, change_rmax):
        r_max = npz_dataset.extra_fixed_fields["r_max"] + change_rmax
        a = NpzDataset(
            file_name=npz_data,
            root=npz_dataset.root,
            extra_fixed_fields={"r_max": r_max},
        )
        print(a.processed_file_names[0])
        print(npz_dataset.processed_file_names[0])
        assert (a.processed_file_names[0] == npz_dataset.processed_file_names[0]) == (
            change_rmax == 0
        )


class TestFromConfig:
    @pytest.mark.parametrize(
        "args",
        [
            dict(extra_fixed_fields={"r_max": 3.0}),
            dict(dataset_extra_fixed_fields={"r_max": 3.0}),
            dict(r_max=3.0),
            dict(r_max=3.0, extra_fixed_fields={}),
        ],
    )
    def test_npz(self, npz_data, root, args):
        config = Config(dict(dataset="npz", file_name=npz_data, root=root, **args))
        g = dataset_from_config(config)
        assert g.fixed_fields["r_max"] == 3
        assert isdir(g.root)
        assert isdir(f"{g.root}/processed")

    def test_ase(self, ase_file, root):
        config = Config(
            dict(
                dataset="ASEDataset",
                file_name=ase_file,
                root=root,
                extra_fixed_fields={"r_max": 3.0},
                ase_args=dict(format="extxyz"),
            )
        )
        a = dataset_from_config(config)
        assert isdir(a.root)
        assert isdir(f"{a.root}/processed")


class TestFromList:
    def test_from_atoms(self, molecules):
        dataset = ASEDataset.from_atoms_list(
            molecules, extra_fixed_fields={"r_max": 4.5}
        )
        assert len(dataset) == len(molecules)
        for i, mol in enumerate(molecules):
            assert np.array_equal(
                mol.get_atomic_numbers(), dataset.get(i).to_ase().get_atomic_numbers()
            )
