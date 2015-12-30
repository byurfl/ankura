"""Functions for finding anchor words from a docwords matrix"""

import numpy

from .util import tuplize


def random_projection(A, k, rng=numpy.random):
    """Randomly reduces the dimensionality of a n x d matrix A to k x d

    We follow the method given by Achlioptas 2001 which yields a projection
    which does well at preserving pairwise distances within some small factor.
    We do this by multiplying A with R, a n x k matrix with each element
    R_{i,j} distributed as:
        sqrt(3)  with probability 1/6
        0        with probability 2/3
        -sqrt(3) with probability 1/ 6
    The resulting matrix therefore has the dimensions k x d so each of the d
    examples in A is reduced from n dimensions to k dimensions.
    """
    R = rng.choice([-1, 0, 0, 0, 0, 1], (A.shape[1], k)) * numpy.sqrt(3)
    return numpy.dot(A, R)


def identify_candidates(M, doc_threshold):
    """Return list of potential anchor words from a sparse docwords matrix

    Candiate anchor words are words which appear in a significant number of
    documents. These are not rarewords persey (or else they would probably be
    filtered during pre-processing), but do not appear in enough documents to
    be useful as an anchor word.
    """
    candidate_anchors = []
    for i in range(M.shape[0]):
        if M[i, :].nnz > doc_threshold:
            candidate_anchors.append(i)
    return candidate_anchors


def gramschmidt_anchors(dataset, k, candidate_threshold, project_dim=1000):
    """Uses stabalized Gram-Schmidt decomposition to find k anchors

    The original Q will not be modified. The anchors are returned in the form
    of a list of k indicies into the original Q. The candidate threshold is
    used to determine which words are eligible to become an anchor.
    """
    # Find candidate words which appear in enough documents to be anchor words
    candidates = identify_candidates(dataset.M, candidate_threshold)

    # don't modify the original Q
    Q = dataset.Q.copy()

    # normalized rows of Q and perform dimensionality reduction
    row_sums = Q.sum(1)
    for i in range(len(Q[:, 0])):
        Q[i, :] = Q[i, :] / float(row_sums[i])
    if project_dim:
        Q = random_projection(Q, project_dim)

    # setup book keeping for gram-schmidt
    anchors = numpy.zeros(k, dtype=numpy.int)
    basis = numpy.zeros((k-1, Q.shape[1]))

    # find the farthest point p1 from the origin
    max_dist = 0
    for i in candidates:
        dist = numpy.dot(Q[i], Q[i])
        if dist > max_dist:
            max_dist = dist
            anchors[0] = i

    # let p1 be the origin of our coordinate system
    for i in candidates:
        Q[i] = Q[i] - Q[anchors[0]]

    # find the farthest point from p1
    max_dist = 0
    for i in candidates:
        dist = numpy.dot(Q[i], Q[i])
        if dist > max_dist:
            max_dist = dist
            anchors[1] = i
            basis[0] = Q[i] / numpy.sqrt(numpy.dot(Q[i], Q[i]))

    # stabilized gram-schmidt to finds new anchor words to expand our subspace
    for j in range(1, k - 1):
        # project all the points onto our basis and find the farthest point
        max_dist = 0
        for i in candidates:
            Q[i] = Q[i] - numpy.dot(Q[i], basis[j-1]) * basis[j - 1]
            dist = numpy.dot(Q[i], Q[i])
            if dist > max_dist:
                max_dist = dist
                anchors[j + 1] = i
                basis[j] = Q[i] / numpy.sqrt(numpy.dot(Q[i], Q[i]))

    return tuplize([anchor] for anchor in anchors)


def constraint_anchors(dataset, constraints):
    """Constructs anchors based on a set of user constraints

    The constraints are given in the form of the string token. Any token which
    is not present in the dataset vocabulary is ignored. The anchors are
    returned as a list of indices for each anchor.
    """
    anchors = []
    for constraint in constraints:
        anchor = []
        for word in constraint:
            try:
                anchor.append(dataset.vocab.index(word))
            except ValueError:
                pass
        anchors.append(anchor)
    return tuplize(anchors)


def anchor_vectors(dataset, anchors):
    """Constructs basis vectors from a list of anchor indices"""
    basis = numpy.zeros((len(anchors), dataset.Q.shape[1]))
    for i, anchor in enumerate(anchors):
        basis[i] = dataset.Q[anchor, :].sum(axis=0) / len(anchor)
    return basis
