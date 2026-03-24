import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from numba import jit
import numba as nb
from typing import Any


# buildindex
def build_index(edges):
	nodelist = sorted({e[0] for e in edges}.union({e[1] for e in edges}))
	nlen = len(nodelist)
	return dict(zip(nodelist, range(nlen)))


def sparse_matrix(edges, index=None):
	if index is None:
		index = build_index(edges)
	nlen = len(index)
	coefficients = zip(*((index[u], index[v], w) for u, v, w in edges))
	row, col, data = coefficients
	return csr_matrix((data, (row, col)), shape=(nlen, nlen)), index


def get_nodes_degree(edges) -> dict[Any, int]:
	"""
	take edges like links[['a','b]].values
	return node degree
	"""
	node_index = build_index(edges)
	index_node = {v: k for k, v in node_index.items()}
	nlen = len(node_index)
	row = np.array([*map(node_index.get, [e[0] for e in edges])], dtype=np.int32)
	col = np.array([*map(node_index.get, [e[1] for e in edges])], dtype=np.int32)
	data = np.ones(len(edges), dtype=bool)
	mat = csr_matrix((data, (row, col)), shape=(nlen, nlen))

	out_degree = np.array(mat.sum(axis=1)).ravel()  # to 1d arr
	in_degree = np.array(mat.sum(axis=0)).ravel()  # to 1d arr

	degree = in_degree + out_degree
	degree_dict = {index_node.get(i): d for i, d in enumerate(degree)}
	return degree_dict


@jit(nopython=True, locals={'predecessors': nb.int32[:, ::1], 'i': nb.int32, 'j': nb.int32})
def get_path(predecessors, i, j):
	path = [j]
	k = j
	p = 0
	while p != -9999:
		k = p = predecessors[i, k]
		path.append(p)
	return path[::-1][1:]


def get_edge_path(p):
	return list(zip(p[:-1], p[1:]))


def get_strongly_connected_component(edges) -> list[Any]:
	"""
	take edges like links[['a','b]].values
	return the nodes that are in the main connected_componant (biggest)
	"""
	node_index = build_index(edges)
	index_node = {v: k for k, v in node_index.items()}
	nlen = len(node_index)
	# create a directed graph
	row = np.array([*map(node_index.get, [e[0] for e in edges])], dtype=np.int32)
	col = np.array([*map(node_index.get, [e[1] for e in edges])], dtype=np.int32)
	data = np.ones(len(edges), dtype=bool)
	mat = csr_matrix((data, (row, col)), shape=(nlen, nlen))
	# get connected components
	_, labels = connected_components(mat, directed=True, connection='strong')
	# get main component.
	counts = np.bincount(labels)
	main_label = np.where(counts == counts.max())[0][0]
	# return only main component nodes
	main_nodes = [index_node.get(i) for i, d in enumerate(labels) if d == main_label]
	return main_nodes
