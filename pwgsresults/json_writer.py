from pwgsresults.index_calculator import IndexCalculator
import json
import gzip
import zipfile
import numpy as np
import scipy.stats

np.seterr(invalid='raise')

def calc_tree_densities(summaries):
  tidxs = sorted(summaries.keys())
  _extract = lambda idxname: np.array([summaries[tidx][idxname] for tidx in tidxs])

  epsilon = 0.0001
  indices = {I: _extract(I + '_index') for I in ('linearity', 'branching', 'clustering')}
  X = indices['clustering']
  # Epsilon prevents division by zero in case of single-node trees.
  Y = indices['branching'] / (indices['branching'] + indices['linearity'] + epsilon)

  # Must be (# dimensions, # data points)
  XY = np.vstack((X, Y))
  # Must conver to Python list so it can be serialized to JSON.

  try:
    density = list(scipy.stats.gaussian_kde(XY)(XY))
  except (np.linalg.linalg.LinAlgError, FloatingPointError):
    # Occurs when sample covariance matrix is singular because, e.g., data lies
    # on manifold. We see this happen when all trees are linear, implying BI=0.
    # To overcome this error, calculate density in 1D without using the BI.
    try:
      density = list(scipy.stats.gaussian_kde(X)(X))
    except (np.linalg.linalg.LinAlgError, FloatingPointError):
      # ... but an exception may still occur if all trees have the same
      # structure, I think. This was triggered when working with Steph's trees,
      # using PhyloSteph.
      density = np.zeros(len(X))

  return dict(zip(tidxs, density))

class JsonWriter(object):
  def __init__(self, dataset_name):
    self._dataset_name = dataset_name

  def write_mutlist(self, mutlist, mutlist_outfn):
    with gzip.GzipFile(mutlist_outfn, 'w') as mutf:
      mutlist['dataset_name'] = self._dataset_name
      json.dump(mutlist, mutf)

  def write_summaries(self, summaries, params, summaries_outfn, gmmClusters):
    to_dump = {
      'dataset_name': self._dataset_name,
      'params': params,
      'trees': summaries,
      'tree_densities': calc_tree_densities(summaries),
      'clusters': gmmClusters
    }
    with gzip.GzipFile(summaries_outfn, 'w') as summf:
      json.dump(to_dump, summf)

  def write_mutass(self, mutass, mutass_outfn):
    with zipfile.ZipFile(mutass_outfn, 'w', compression=zipfile.ZIP_DEFLATED) as muts_file:
      for tree_idx, tree_mutass in mutass.items():
        to_dump = {
          'mut_assignments': tree_mutass,
          'dataset_name': self._dataset_name
        }
        muts_file.writestr('%s.json' % tree_idx, json.dumps(to_dump))

