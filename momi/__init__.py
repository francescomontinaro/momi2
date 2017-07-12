"""
momi (MOran Models for Inference) is a python package for computing the site frequency spectrum,
a summary statistic commonly used in population genetics, and using it to infer demographic history.

Please refer to examples/tutorial.ipynb for usage & introduction.
"""
from .parse_ms import simulate_ms, run_ms, to_ms_cmd, seg_sites_from_ms
from .demography import demographic_history, make_demography
from .compute_sfs import expected_sfs, expected_total_branch_len, expected_sfs_tensor_prod, expected_tmrca, expected_deme_tmrca
from .likelihood import SfsLikelihoodSurface
from .confidence_region import ConfidenceRegion
from .data.config_array import config_array
from .data.sfs import site_freq_spectrum
from .data.tensor import sfs_tensor_prod
from .data.seg_sites import write_seg_sites, read_seg_sites, seg_site_configs
from .data.plink import read_plink_frq_strat
from .data.snps import SnpAlleleCounts
from .demo_model import demographic_model
