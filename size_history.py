#from __future__ import division
from util import EPSILON, memoize
import autograd.numpy as np
from autograd.numpy import sum, exp, log, expm1
from autograd.core import primitive
from cached_property import cached_property
import scipy.integrate
from scipy.special import comb as binom
import scipy.special
import moran_model

@memoize
def W(n, b, j):
    if j == 2:
        return 6.0 / float(n + 1)
    elif j == 3:
        return 30.0 * (n - 2 * b) / float(n + 1) / float(n + 2)
    else:
        jj = float(j - 2)
        ret = W(n, b, jj) * -(1 + jj) * (3 + 2 * jj) * (n - jj) / jj / (2 * jj - 1) / (n + jj + 1)
        ret += W(n, b, jj + 1) * (3 + 2 * jj) * (n - 2 * b) / jj / (n + jj + 1)
        return ret

class TruncatedSizeHistory(object):
    def __init__(self, n_max, tau):
        self.n_max = n_max
        self.tau = tau

    def freq(self, n_derived, n):
        if n_derived == 0:
            return 0.0
        return self.sfs[(n_derived, n)]

    @cached_property
    def sfs(self):
        if self.n_max == 1:
            return {(1, 1): self.tau}
        ret = {}
        # compute the SFS for n_max via Polanski and Kimmel
        ww = np.zeros([self.n_max - 1, self.n_max - 1])
        for i in range(2, self.n_max + 1):
            for j in range(1, self.n_max):
                ww[i - 2, j - 1] = W(self.n_max, j, i)
        bv = (self.etjj[:, None] * ww).sum(axis=0) ## Keep ADF object on the left
        ret = dict(((b, self.n_max), v) for b, v in enumerate(bv, 1))
        # compute entry for monomorphic site
        ret[(self.n_max, self.n_max)] = self._before_tmrca(ret)

        # use recurrence to compute SFS for n < maxSampleSize
        ### TODO: these SFS entries aren't currently necessary, though perhaps we will
        ### need them in the future.
#         for n in range(self.n_max - 1, 0, -1):
#             for k in range(1, n + 1):
#                 ret[(k, n)] = (ret[(k + 1, n + 1)] * (k + 1) / (n + 1) + 
#                         ret[(k, n + 1)] * (n + 1 - k) / (n + 1))

#         # check accuracy
#         assert self.tau == ret[(1, 1)] or abs(log(self.tau / ret[(1, 1)])) < EPSILON, \
#                 "%.16f, %.16f"  % (self.tau, ret[(1, 1)])

        ## TODO: add non-negativity checks back!!
#         for _,v in ret.iteritems():
#             truncate(v, level=min(1e-16, float(self.tau)*1e-15))
#         assert all([v >= 0.0 for _,v in ret.iteritems()])
        return ret

    def _before_tmrca(self, partial_sfs):
        return self.tau - sum([partial_sfs[(b, self.n_max)] * b / float(self.n_max)
                               for b in range(1, self.n_max)])


    def transition_prob(self, v, axis=0):
        if self.scaled_time == 0.0:
            ### TODO: make deep copy
            return v
        return moran_model.moran_action(self.scaled_time, v, axis=axis)


class ConstantTruncatedSizeHistory(TruncatedSizeHistory):
    '''Constant size population truncated to time tau.'''
    def __init__(self, n_max, tau, N):
        super(ConstantTruncatedSizeHistory, self).__init__(n_max, tau)
        if N <= 0.0:
            raise Exception("N must be positive")
        self.N = N

    @cached_property
    def etjj(self):
        j = np.arange(2, self.n_max + 1)

        denom = binom(j, 2) / self.N
        if self.tau == float('inf'):
            return 1.0 / denom

        scaled_time = denom * self.tau
        num = -expm1(-scaled_time) # equals 1 - exp(-scaledTime)
        ret = num / denom
        ## TODO: add back assertion!
        #epsilon = 1e-15*float(self.tau)
        #assert np.all(ret[:-1] - ret[1:] >= -epsilon) and np.all(ret >= -epsilon) and np.all(ret <= self.tau + epsilon)
        return ret
    
    @cached_property
    def scaled_time(self):
        '''
        integral of 1/haploidN(t) from 0 to tau.
        used for Moran model transitions
        '''
        return self.tau / self.N

    def __str__(self):
        return "(ConstantPopSize: N=%f, tau=%f)" % (self.N, self.tau)

'''
Returns
-expi(-1/x) * exp(1/x) / x
for x s.t. abs(x) is decreasing
'''
def transformed_expi(x):
    abs_x = np.abs(x)
    # TODO: remove this assertion/assumption, whenever autograd implements np.__set__
    assert np.all(abs_x[:-1] >= abs_x[1:])
    ser = abs_x < 1./45.
    nser = np.logical_not(ser)

    return np.concatenate((transformed_expi_series(x[ser]), transformed_expi_naive(x[nser])))

# def transformed_expi_grad(ans,x):
#     is_zero = np.all(x == 0.0)
#     ## autograd currently doesn't support indexing, so all vector entries must be entirely in one case or the other
#     assert is_zero or np.all(x != 0.0)
#     if is_zero:
#         return lambda g: -1. * g
#     else:
#         return lambda g: g * (-1./x**2) * (-1. + ans + ans*x) 
# transformed_expi.defgrad(transformed_expi_grad)

def transformed_expi_series(x):
    c_n, ret = 1., 1.
    for n in range(1,11):
        c_n = -c_n * x * n
        ret = ret + c_n
    return ret

def transformed_expi_naive(x):
    return -expi(-1.0/x) * exp(1.0/x) / x

@primitive
def expi(x):
    return scipy.special.expi(x)
expi.defgrad(lambda ans,x: lambda g: g * exp(x) / x)

'''
returns (e^x-1)/x, for scalar x. works for x=0.
Taylor series is 1 + x/2! + x^2/3! + ...
'''
def expm1d(x):
    if x == 0.0:
        return expm1d_taylor(x)
    return expm1(x)/x
## used for higher order derivatives at x=0
def expm1d_taylor(x):
    c_n, ret = 1.,1.
    for n in range(2,11):
        c_n = c_n * x / float(n)
        ret = ret + c_n
    return ret
    

class ExponentialTruncatedSizeHistory(TruncatedSizeHistory):
    ## some computations here are done in a seemingly roundabout way,
    ## to ensure that growth_rate=0.0 works
    ## TODO: tau == inf not yet tested (maybe just use tau=1e200 instead)
    def __init__(self, n_max, tau, N_top, N_bottom):
        super(ExponentialTruncatedSizeHistory, self).__init__(n_max, tau)
        self.N_top, self.N_bottom = N_top, N_bottom
        # N_bottom = N_top * exp(tau * growth_rate)
        self.growth_rate = log(self.N_bottom / self.N_top) / self.tau

    @cached_property
    def etjj(self):
        j = np.arange(2, self.n_max+1)
        jChoose2 = scipy.misc.comb(j,2)

        pow0, pow1 = self.N_bottom/jChoose2 , self.growth_rate*self.tau
        ret = -transformed_expi(pow0 * self.growth_rate / exp(pow1))
        ret = ret * exp(-expm1d(pow1) * self.tau / pow0 - pow1)
        ret = ret + transformed_expi(pow0 * self.growth_rate)
        ret = ret * pow0

        assert np.all(ret[1:] - ret[:-1] <= 0) # ret should be decreasing
        assert np.all(ret >= 0)
        assert np.all(ret <= self.tau)

        return ret

    @cached_property
    def scaled_time(self):
        '''
        integral of 1/haploidN(t) from 0 to tau.
        used for Moran model transitions
        '''
        return expm1d(self.growth_rate * self.tau) * self.tau / self.N_bottom

class FunctionalTruncatedSizeHistory(TruncatedSizeHistory):
    '''Size history parameterized by an arbitrary function f.'''
    def __init__(self, n_max, tau, f):
        '''Initialize the model. For t > 0, f(t) >= is the instantaneous
        rate of coalescence (i.e., the inverse of the population size).
        f should accept and return vectors of times.
        '''
        super(FunctionalTruncatedSizeHistory, self).__init__(n_max, tau)
        self._f = f

    def _R(self, t):
        return scipy.integrate.quad(self._f, 0, t)[0]

    @cached_property
    def etjj(self):
        ret = []
        # TODO: if this is too slow for large n_max, it could be sped up
        # by using vectorized integration (a la scipy.integrate.simps)
        for j in range(2, self.n_max + 1):
            j2 = binom(j, 2)
            # tau * P(Tjj > tau)
            r1 = self.tau * exp(-j2 * self.scaled_time)
            def _int(t):
                return t * self._f(t) * exp(-j2 * self._R(t))
            r2 = scipy.integrate.quad(_int, 0, self.tau)[0]
            ret.append(r1 + j2 * r2)
        return ret

    @cached_property
    def scaled_time(self):
        return self._R(self.tau)


class PiecewiseHistory(TruncatedSizeHistory):
    def __init__(self, pieces):
        n_max = pieces[0].n_max
        assert all([p.n_max == n_max for p in pieces])
        tau = sum([p.tau for p in pieces])
        super(PiecewiseHistory, self).__init__(n_max, tau)
        self.pieces = pieces

    @cached_property
    def etjj(self):
        j = np.arange(2, self.n_max+1)
        jChoose2 = scipy.misc.comb(j,2)

        ret = np.zeros(len(j))
        noCoalProb = np.ones(len(j))
        for pop in self.pieces:
            ret = ret + noCoalProb * pop.etjj
            if pop.scaled_time != float('inf'):
                ## WARNING: autodifferentiate will break if jChoose2 * pop.scaled_time (the reverse order)
                noCoalProb = noCoalProb * exp(- pop.scaled_time * jChoose2)
            else:
                assert pop is self.pieces[-1]
        return ret

    @cached_property
    def scaled_time(self):
        if self.tau == float('inf'):
            return self.tau
        return sum([pop.scaled_time for pop in self.pieces])
