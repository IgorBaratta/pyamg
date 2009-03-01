"""Relaxation methods for linear systems"""

__docformat__ = "restructuredtext en"

from warnings import warn

import numpy
from scipy import sparse

from pyamg.util.utils import type_prep, get_diagonal
from pyamg import amg_core


__all__ = ['sor', 'gauss_seidel', 'jacobi', 'polynomial']
__all__ += ['kaczmarz_jacobi', 'kaczmarz_richardson', 'kaczmarz_gauss_seidel']
__all__ += ['gauss_seidel_indexed'] 

def make_system(A, x, b, formats=None):
    """
    Return A,x,b suitable for relaxation or raise an exception
    
    Parameters
    ----------
    A : {sparse-matrix}
        n x n system
    x : {array}
        n-vector, initial guess
    b : {array}
        n-vector, right-hand side
    formats: {'csr', 'csc', 'bsr', 'lil', 'dok',...}
        desired sparse matrix format
        default is no change to A's format

    Returns
    -------
    (A,x,b), where A is in the desired sparse-matrix format
    and x and b are "raveled", i.e. (n,) vectors.

    Notes
    -----
    Does some rudimentary error checking on the system,
    such as checking for compatible dimensions and checking
    for compatible type, i.e. float or complex.

    Examples
    --------
    >>> from pyamg.relaxation.relaxation import make_system 
    >>> from pyamg.gallery import poisson
    >>> from scipy import rand, zeros, ones, array, mean
    >>> A = poisson((50,50), format='csr')
    >>> x = zeros((A.shape[0],1))
    >>> b = rand(A.shape[0],1)
    >>> (A,x,b) = make_system(A,x,b,formats=['csc'])
    >>> print "x.shape = " + str(x.shape)
    >>> print "b.shape = " + str(b.shape)
    >>> print "A.format = " + A.format
    """

    if formats is None:
        pass
    elif formats == ['csr']:
        if sparse.isspmatrix_csr(A):
            pass
        elif sparse.isspmatrix_bsr(A):
            A = A.tocsr()
        else:
            warn('implicit conversion to CSR', sparse.SparseEfficiencyWarning)
            A = sparse.csr_matrix(A)
    else:
        if sparse.isspmatrix(A) and A.format in formats:
            pass
        else:
            A = sparse.csr_matrix(A).asformat(formats[0])

    if not isinstance(x, numpy.ndarray):
        raise ValueError('expected numpy array for argument x')
    if not isinstance(b, numpy.ndarray):
        raise ValueError('expected numpy array for argument b')

    M,N = A.shape

    if M != N:
        raise ValueError('expected square matrix')

    if x.shape not in [(M,), (M,1)]:
        raise ValueError('x has invalid dimensions')
    if b.shape not in [(M,), (M,1)]:
        raise ValueError('b has invalid dimensions')

    if A.dtype != x.dtype or A.dtype != b.dtype:
        raise TypeError('arguments A, x, and b must have the same dtype')
    
    if not x.flags.carray:
        raise ValueError('x must be contiguous in memory')

    x = numpy.ravel(x)
    b = numpy.ravel(b)

    return A,x,b

def sor(A, x, b, omega, iterations=1, sweep='forward'):
    """Perform SOR iteration on the linear system Ax=b

    Parameters
    ----------
    A : {csr_matrix, bsr_matrix}
        Sparse NxN matrix
    x : ndarray
        Approximate solution (length N)
    b : ndarray
        Right-hand side (length N)
    omega : scalar
        Damping parameter
    iterations : int
        Number of iterations to perform
    sweep : {'forward','backward','symmetric'}
        Direction of sweep

    Returns
    -------
    Nothing, x will be modified in place.
   
    Notes
    -----
    When omega=1.0, SOR is equivalent to Gauss-Seidel.

    Examples
    --------
    >>> ## Use SOR as stand-along solver
    >>> from pyamg.relaxation import sor
    >>> from pyamg.gallery import poisson
    >>> from pyamg.util.linalg import norm
    >>> from scipy import rand, zeros, ones, array, mean
    >>> A = poisson((50,50), format='csr')
    >>> x0 = zeros((A.shape[0],1))
    >>> b = rand(A.shape[0],1)
    >>> r0 = norm(b - A*x0)
    >>> sor(A, x0, b, 1.33, iterations=10)
    >>> print "Initial Residual:  %1.2e"%r0
    >>> print "Residual After 10 SOR Sweeps:  %1.2e"%norm(b-A*x0)
    >>>
    >>> ## Use SOR as the multigrid smoother 
    >>> from pyamg import smoothed_aggregation_solver
    >>> sa = smoothed_aggregation_solver(A, B=ones((A.shape[0],1)),
                coarse_solver='pinv2', max_coarse=50,
                presmoother=('sor', {'sweep':'symmetric', 'omega' : 1.33}), 
                postsmoother=('sor', {'sweep':'symmetric', 'omega' : 1.33}))
    >>> x0=zeros((A.shape[0],1))
    >>> residuals=[]
    >>> x = sa.solve(b, x0=x0, tol=1e-8, residuals=residuals)
    >>> residuals = array(residuals)
    >>> print "Relative Residual After AMG Solve:  %1.2e"%(norm(b-A*x)/norm(b))
    >>> print "Average Residual Reduction Factor %1.2f"%mean(residuals[1:]/residuals[0:-1])
    """
    A,x,b = make_system(A, x, b, formats=['csr','bsr'])

    x_old = numpy.empty_like(x)

    for i in range(iterations):
        x_old[:] = x

        gauss_seidel(A, x, b, iterations=1, sweep=sweep)
        
        x     *= omega
        x_old *= (1-omega)
        x     += x_old


def gauss_seidel(A, x, b, iterations=1, sweep='forward'):
    """Perform Gauss-Seidel iteration on the linear system Ax=b

    Parameters
    ----------
    A : {csr_matrix, bsr_matrix}
        Sparse NxN matrix
    x : ndarray
        Approximate solution (length N)
    b : ndarray
        Right-hand side (length N)
    iterations : int
        Number of iterations to perform
    sweep : {'forward','backward','symmetric'}
        Direction of sweep

    Returns
    -------
    Nothing, x will be modified in place.

    Examples
    --------
    >>> ## Use Gauss-Seidel as a Stand-Alone Solver
    >>> from pyamg.relaxation import *
    >>> from pyamg.gallery import poisson
    >>> from pyamg.util.linalg import norm
    >>> from scipy import rand, zeros, ones, array, mean
    >>> A = poisson((50,50), format='csr')
    >>> x0 = zeros((A.shape[0],1))
    >>> b = rand(A.shape[0],1)
    >>> r0 = norm(b - A*x0)
    >>> gauss_seidel(A, x0, b, iterations=10)
    >>> print "Initial Residual:  %1.2e"%r0
    >>> print "Residual After 10 Gauss-Seidel Sweeps:  %1.2e"%norm(b-A*x0)
    >>> 
    >>> ## Use Gauss-Seidel as the Multigrid Smoother
    >>> from pyamg import smoothed_aggregation_solver
    >>> sa = smoothed_aggregation_solver(A, B=ones((A.shape[0],1)),
    >>>         coarse_solver='pinv2', max_coarse=50,
    >>>         presmoother=('gauss_seidel', {'sweep':'symmetric'}), 
    >>>         postsmoother=('gauss_seidel', {'sweep':'symmetric'}))
    >>> x0=zeros((A.shape[0],1))
    >>> residuals=[]
    >>> x = sa.solve(b, x0=x0, tol=1e-8, residuals=residuals)
    >>> residuals = array(residuals)
    >>> print "Relative Residual After AMG Solve:  %1.2e"%(norm(b-A*x)/norm(b))
    >>> print "Average Residual Reduction Factor %1.2f"%mean(residuals[1:]/residuals[0:-1])
    """
    A,x,b = make_system(A, x, b, formats=['csr','bsr'])

    if sweep == 'forward':
        row_start,row_stop,row_step = 0,len(x),1
    elif sweep == 'backward':
        row_start,row_stop,row_step = len(x)-1,-1,-1 
    elif sweep == 'symmetric':
        for iter in xrange(iterations):
            gauss_seidel(A, x, b, iterations=1, sweep='forward')
            gauss_seidel(A, x, b, iterations=1, sweep='backward')
        return
    else:
        raise ValueError("valid sweep directions are 'forward', 'backward', and 'symmetric'")


    if sparse.isspmatrix_csr(A):
        for iter in xrange(iterations):
            amg_core.gauss_seidel(A.indptr, A.indices, A.data,
                                        x, b,
                                        row_start, row_stop, row_step)
    else:
        R,C = A.blocksize
        if R != C:
            raise ValueError('BSR blocks must be square')
        row_start = row_start / R
        row_stop  = row_stop  / R
        for iter in xrange(iterations):
            amg_core.block_gauss_seidel(A.indptr, A.indices, numpy.ravel(A.data),
                                              x, b,
                                              row_start, row_stop, row_step,
                                              R)


def jacobi(A, x, b, iterations=1, omega=1.0):
    """Perform Jacobi iteration on the linear system Ax=b

    Parameters
    ----------
    A : csr_matrix
        Sparse NxN matrix
    x : ndarray
        Approximate solution (length N)
    b : ndarray
        Right-hand side (length N)
    iterations : int
        Number of iterations to perform
    omega : scalar
        Damping parameter

    Returns
    -------
    Nothing, x will be modified in place.
   
    Examples
    --------
    >>> ## Use Jacobi as a Stand-Alone Solver
    >>> from pyamg.relaxation import *
    >>> from pyamg.gallery import poisson
    >>> from pyamg.util.linalg import norm
    >>> from scipy import rand, zeros, ones, array, mean
    >>> A = poisson((50,50), format='csr')
    >>> x0 = zeros((A.shape[0],1))
    >>> b = rand(A.shape[0],1)
    >>> r0 = norm(b - A*x0)
    >>> jacobi(A, x0, b, iterations=10, omega=1.0)
    >>> print "Initial Residual:  %1.2e"%r0
    >>> print "Residual After 10 w-Jacobi Sweeps:  %1.2e"%norm(b-A*x0)
    >>> 
    >>> ## Use Jacobi as the Multigrid Smoother
    >>> from pyamg import smoothed_aggregation_solver
    >>> sa = smoothed_aggregation_solver(A, B=ones((A.shape[0],1)),
    >>>         coarse_solver='pinv2', max_coarse=50,
    >>>         presmoother=('jacobi', {'omega': 4.0/3.0, 'iterations' : 2}), 
    >>>         postsmoother=('jacobi', {'omega': 4.0/3.0, 'iterations' : 2}))
    >>> x0=zeros((A.shape[0],1))
    >>> residuals=[]
    >>> x = sa.solve(b, x0=x0, tol=1e-8, residuals=residuals)
    >>> residuals = array(residuals)
    >>> print "Relative Residual After AMG Solve:  %1.2e"%(norm(b-A*x)/norm(b))
    >>> print "Average Residual Reduction Factor %1.2f"%mean(residuals[1:]/residuals[0:-1])
    """
    A,x,b = make_system(A, x, b, formats=['csr'])

    sweep = slice(None)
    (row_start,row_stop,row_step) = sweep.indices(A.shape[0])

    if (row_stop - row_start) * row_step <= 0:  #no work to do
        return

    temp = numpy.empty_like(x)
    
    # Create uniform type, and convert possibly complex scalars to length 1 arrays
    [omega] = type_prep(A.dtype, [omega])

    for iter in xrange(iterations):
        amg_core.jacobi(A.indptr, A.indices, A.data,
                              x, b, temp,
                              row_start, row_stop, row_step,
                              omega)


def polynomial(A, x, b, coeffients, iterations=1):
    """Apply a polynomial smoother to the system Ax=b


    Parameters
    ----------
    A : sparse matrix
        Sparse NxN matrix
    x : ndarray
        Approximate solution (length N)
    b : ndarray
        Right-hand side (length N)
    coeffients : {array_like}
        Coefficients of the polynomial.  See Notes section for details.
    iterations : int
        Number of iterations to perform

    Returns
    -------
    Nothing, x will be modified in place.

    Notes
    -----
    The smoother has the form  x[:] = x + p(A) (b - A*x) where p(A) is a 
    polynomial in A whose scalar coeffients are specified (in decending 
    order) by argument 'coeffients'.

    - Richardson iteration p(A) = c_0:
        polynomial_smoother(A, x, b, [c_0])

    - Linear smoother p(A) = c_1*A + c_0:
        polynomial_smoother(A, x, b, [c_1, c_0])

    - Quadratic smoother p(A) = c_2*A^2 + c_1*A + c_0:
        polynomial_smoother(A, x, b, [c_2, c_1, c_0])

    Here, Horner's Rule is applied to avoid computing A^k directly.  
    
    For efficience, the method detects the case x = 0 one matrix-vector 
    product is avoided (since (b - A*x) is b).

    Examples
    --------
    >>> ## The polynomial smoother is not currently used directly 
    >>> ## in PyAMG.  It is only used by the chebyshev smoothing option,
    >>> ## which automatically calculates the correct coefficients.
    >>> from pyamg.gallery import poisson
    >>> from pyamg.util.linalg import norm
    >>> from scipy import rand, zeros, ones, array, mean
    >>> from pyamg import smoothed_aggregation_solver
    >>> A = poisson((50,50), format='csr')
    >>> b = rand(A.shape[0],1)
    >>> sa = smoothed_aggregation_solver(A, B=ones((A.shape[0],1)),
    >>>         coarse_solver='pinv2', max_coarse=50,
    >>>         presmoother=('chebyshev', {'degree':3, 'iterations':1}), 
    >>>         postsmoother=('chebyshev', {'degree':3, 'iterations':1}))
    >>> x0=zeros((A.shape[0],1))
    >>> residuals=[]
    >>> x = sa.solve(b, x0=x0, tol=1e-8, residuals=residuals)
    >>> residuals = array(residuals)
    >>> print "Relative Residual After AMG Solve:  %1.2e"%(norm(b-A*x)/norm(b))
    >>> print "Average Residual Reduction Factor %1.2f"%mean(residuals[1:]/residuals[0:-1])
    """
    A,x,b = make_system(A, x, b, formats=None)

    for i in range(iterations):
        from pyamg.util.linalg import norm

        if norm(x) == 0:
            residual = b
        else:
            residual = (b - A*x)

        h = coeffients[0]*residual
    
        for c in coeffients[1:]:
            h = c*residual + A*h
    
        x += h


def gauss_seidel_indexed(A, x, b,  indices, iterations=1, sweep='forward'):
    """Perform indexed Gauss-Seidel iteration on the linear system Ax=b

    In indexed Gauss-Seidel, the sequence in which unknowns are relaxed is
    specified explicitly.  In contrast, the standard Gauss-Seidel method
    always performs complete sweeps of all variables in increasing or 
    decreasing order.  The indexed method may be used to implement 
    specialized smoothers, like F-smoothing in Classical AMG.

    Parameters
    ----------
    A : csr_matrix
        Sparse NxN matrix
    x : ndarray
        Approximate solution (length N)
    b : ndarray
        Right-hand side (length N)
    indices : ndarray
        Row indices to relax.
    iterations : int
        Number of iterations to perform
    sweep : {'forward','backward','symmetric'}
        Direction of sweep

    Returns
    -------
    Nothing, x will be modified in place.

    Examples
    --------
    >>> from pyamg.gallery import poisson
    >>> from numpy import array
    >>> A = poisson((4,), format='csr')
    >>> x = array([0.0, 0.0, 0.0, 0.0])
    >>> b = array([0.0, 1.0, 2.0, 3.0])
    >>> gauss_seidel_indexed(A, x, b, [0,1,2,3])                #relax all four rows, in order
    >>> gauss_seidel_indexed(A, x, b, [0,1])                    #relax first two rows
    >>> gauss_seidel_indexed(A, x, b, [2,0])                    #relax row 2, then row 0
    >>> gauss_seidel_indexed(A, x, b, [2,3], sweep='backward')  #relax row 3, then row 2
    >>> gauss_seidel_indexed(A, x, b, [2,0,2])                  #relax row 2, then 0, then 2 again

    """
    A,x,b = make_system(A, x, b, formats=['csr'])

    indices = numpy.asarray(indices, dtype='intc')

    #if indices.min() < 0:
    #    raise ValueError('row index (%d) is invalid' % indices.min())
    #if indices.max() >= A.shape[0]
    #    raise ValueError('row index (%d) is invalid' % indices.max())

    if sweep == 'forward':
        row_start,row_stop,row_step = 0,len(indices),1
    elif sweep == 'backward':
        row_start,row_stop,row_step = len(indices)-1,-1,-1 
    elif sweep == 'symmetric':
        for iter in xrange(iterations):
            gauss_seidel_indexed(A, x, b, indices, iterations=1, sweep='forward')
            gauss_seidel_indexed(A, x, b, indices, iterations=1, sweep='backward')
        return
    else:
        raise ValueError('valid sweep directions are \'forward\', \'backward\', and \'symmetric\'')

    for iter in xrange(iterations):
        amg_core.gauss_seidel_indexed(A.indptr, A.indices, A.data,
                                            x, b, indices,
                                            row_start, row_stop, row_step)

def kaczmarz_jacobi(A, x, b, iterations=1, omega=1.0):
    """Perform Kaczmarz Jacobi iterations on the linear system A A^T x = A^Tb
       (Also known as Cimmino relaxation)
    
    Parameters
    ----------
    A : csr_matrix
        Sparse NxN matrix
    x : ndarray
        Approximate solution (length N)
    b : ndarray
        Right-hand side (length N)
    iterations : int
        Number of iterations to perform
    omega : scalar
        Damping parameter

    Returns
    -------
    Nothing, x will be modified in place.

    References
    ----------
    .. [1] Brandt, Ta'asan.  
       "Multigrid Method For Nearly Singular And Slightly Indefinite Problems."
       1985.  NASA Technical Report Numbers: ICASE-85-57; NAS 1.26:178026; NASA-CR-178026;

    .. [2] Kaczmarz.  Angenaeherte Aufloesung von Systemen Linearer Gleichungen. 
       Bull. Acad.  Polon. Sci. Lett. A 35, 355-57.  1937 

    .. [3] Cimmino. La ricerca scientifica ser. II 1. 
       Pubbliz. dell'Inst. pre le Appl. del Calculo 34, 326-333, 1938.
    
    Examples
    --------
    >>> ## Use Kaczmarz Jacobi as a Stand-Alone Solver
    >>> from pyamg.relaxation import *
    >>> from pyamg.gallery import poisson
    >>> from pyamg.util.linalg import norm
    >>> from scipy import rand, zeros, ones, array, mean
    >>> A = poisson((50,50), format='csr')
    >>> x0 = zeros((A.shape[0],1))
    >>> b = rand(A.shape[0],1)
    >>> r0 = norm(b - A*x0)
    >>> kaczmarz_jacobi(A, x0, b, iterations=10, omega=2.0/3.0)
    >>> print "Initial Residual:  %1.2e"%r0
    >>> print "Residual After 10 Kaczmarz-Jacobi Sweeps:  %1.2e"%norm(b-A*x0)
    >>> 
    >>> ## Use Kaczmarz Jacobi as the Multigrid Smoother
    >>> from pyamg import smoothed_aggregation_solver
    >>> sa = smoothed_aggregation_solver(A, B=ones((A.shape[0],1)),
    >>>         coarse_solver='pinv2', max_coarse=50,
    >>>         presmoother=('kaczmarz_jacobi', {'iterations' : 2, 'omega' : 4.0/3.0}), 
    >>>         postsmoother=('kaczmarz_jacobi', {'iterations' : 2, 'omega' : 4.0/3.0}))
    >>> x0=zeros((A.shape[0],1))
    >>> residuals=[]
    >>> x = sa.solve(b, x0=x0, tol=1e-8, residuals=residuals)
    >>> residuals = array(residuals)
    >>> print "Relative Residual After AMG Solve:  %1.2e"%(norm(b-A*x)/norm(b))
    >>> print "Average Residual Reduction Factor %1.2f"%mean(residuals[1:]/residuals[0:-1])
    """
    A,x,b = make_system(A, x, b, formats=['csr'])
    
    sweep = slice(None)
    (row_start,row_stop,row_step) = sweep.indices(A.shape[0])
    
    temp = numpy.zeros_like(x)
    
    # Dinv for A*A.H
    Dinv = get_diagonal(A, norm_eq=2, inv=True)
    
    
    # Create uniform type, and convert possibly complex scalars to length 1 arrays
    [omega] = type_prep(A.dtype, [omega])
    
    for i in range(iterations):
        delta = (numpy.ravel(b - A*x)*numpy.ravel(Dinv)).astype(A.dtype)
        amg_core.kaczmarz_jacobi(A.indptr, A.indices, A.data,
                                       x, b, delta, temp, row_start,
                                       row_stop, row_step, omega)  
    
def kaczmarz_richardson(A, x, b, iterations=1, omega=1.0):
    """Perform Kaczmarz Richardson iterations on the linear system A A^T x = A^Tb
    
    Parameters
    ----------
    A : csr_matrix
        Sparse NxN matrix
    x : ndarray
        Approximate solution (length N)
    b : ndarray
        Right-hand side (length N)
    iterations : int
        Number of iterations to perform
    omega : scalar
        Damping parameter

    Returns
    -------
    Nothing, x will be modified in place.
    
    References
    ----------
    .. [1] Brandt, Ta'asan.  
       "Multigrid Method For Nearly Singular And Slightly Indefinite Problems."
       1985.  NASA Technical Report Numbers: ICASE-85-57; NAS 1.26:178026; NASA-CR-178026;

    .. [2] Kaczmarz.  Angenaeherte Aufloesung von Systemen Linearer Gleichungen. 
       Bull. Acad.  Polon. Sci. Lett. A 35, 355-57.  1937 
 
    Examples
    --------
    >>> ## Use Kaczmarz Richardson as the Multigrid Smoother
    >>> from pyamg import smoothed_aggregation_solver
    >>> from pyamg.gallery import poisson
    >>> from pyamg.util.linalg import norm
    >>> from scipy import rand, zeros, ones, array, mean
    >>> A = poisson((50,50), format='csr')
    >>> b = rand(A.shape[0],1)
    >>> sa = smoothed_aggregation_solver(A, B=ones((A.shape[0],1)),
    >>>         coarse_solver='pinv2', max_coarse=50,
    >>>         presmoother=('kaczmarz_richardson', {'iterations' : 2, 'omega' : 5.0/3.0}), 
    >>>         postsmoother=('kaczmarz_richardson', {'iterations' : 2, 'omega' : 5.0/3.0}))
    >>> x0=zeros((A.shape[0],1))
    >>> residuals=[]
    >>> x = sa.solve(b, x0=x0, tol=1e-8, residuals=residuals)
    >>> residuals = array(residuals)
    >>> print "Relative Residual After AMG Solve:  %1.2e"%(norm(b-A*x)/norm(b))
    >>> print "Average Residual Reduction Factor %1.2f"%mean(residuals[1:]/residuals[0:-1])
    """

    A,x,b = make_system(A, x, b, formats=['csr'])
    
    sweep = slice(None)
    (row_start,row_stop,row_step) = sweep.indices(A.shape[0])
    
    temp = numpy.zeros_like(x)
    
    # Create uniform type, and convert possibly complex scalars to length 1 arrays
    [omega] = type_prep(A.dtype, [omega])
    
    for i in range(iterations):
        delta = numpy.ravel(b - A*x).astype(A.dtype)
        amg_core.kaczmarz_jacobi(A.indptr, A.indices, A.data,
                                           x, b, delta, temp, row_start,
                                           row_stop, row_step, omega)

def kaczmarz_gauss_seidel(A, x, b, iterations=1, sweep='forward'):
    """Perform Kaczmarz Gauss-Seidel iterations on the linear system A A^T x = A^Tb
    
    Parameters
    ----------
    A : csr_matrix
        Sparse NxN matrix
    x : { ndarray }
        Approximate solution (length N)
    b : { ndarray }
        Right-hand side (length N)
    iterations : { int }
        Number of iterations to perform
    sweep : {'forward','backward','symmetric'}
        Direction of sweep

    Returns
    -------
    Nothing, x will be modified in place.
    
    References
    ----------
    .. [1] Brandt, Ta'asan.  
       "Multigrid Method For Nearly Singular And Slightly Indefinite Problems."
       1985.  NASA Technical Report Numbers: ICASE-85-57; NAS 1.26:178026; NASA-CR-178026;

    .. [2] Kaczmarz.  Angenaeherte Aufloesung von Systemen Linearer Gleichungen. 
       Bull. Acad.  Polon. Sci. Lett. A 35, 355-57.  1937 
    
    Examples
    --------
    >>> ## Use Kaczmarz Gauss-Seidel as a Stand-Alone Solver
    >>> from pyamg.relaxation import *
    >>> from pyamg.gallery import poisson
    >>> from pyamg.util.linalg import norm
    >>> from scipy import rand, zeros, ones, array, mean
    >>> A = poisson((50,50), format='csr')
    >>> x0 = zeros((A.shape[0],1))
    >>> b = rand(A.shape[0],1)
    >>> r0 = norm(b - A*x0)
    >>> kaczmarz_gauss_seidel(A, x0, b, iterations=10, sweep='symmetric')
    >>> print "Initial Residual:  %1.2e"%r0
    >>> print "Residual After 10 Kaczmarz Gauss-Seidel Sweeps:  %1.2e"%norm(b-A*x0)
    >>> 
    >>> ## Use Kaczmarz Gauss-Seidel as the Multigrid Smoother
    >>> from pyamg import smoothed_aggregation_solver
    >>> sa = smoothed_aggregation_solver(A, B=ones((A.shape[0],1)),
    >>>         coarse_solver='pinv2', max_coarse=50,
    >>>         presmoother=('kaczmarz_gauss_seidel', {'sweep' : 'symmetric'}), 
    >>>         postsmoother=('kaczmarz_gauss_seidel', {'sweep' : 'symmetric'}))
    >>> x0=zeros((A.shape[0],1))
    >>> residuals=[]
    >>> x = sa.solve(b, x0=x0, tol=1e-8, residuals=residuals)
    >>> residuals = array(residuals)
    >>> print "Relative Residual After AMG Solve:  %1.2e"%(norm(b-A*x)/norm(b))
    >>> print "Average Residual Reduction Factor %1.2f"%mean(residuals[1:]/residuals[0:-1])
    """
    
    A,x,b = make_system(A, x, b, formats=['csr'])
    
    if sweep == 'forward':
        row_start,row_stop,row_step = 0,len(x),1
    elif sweep == 'backward':
        row_start,row_stop,row_step = len(x)-1,-1,-1 
    elif sweep == 'symmetric':
        for iter in xrange(iterations):
            kaczmarz_gauss_seidel(A, x, b, iterations=1, sweep='forward')
            kaczmarz_gauss_seidel(A, x, b, iterations=1, sweep='backward')
        return
    else:
        raise ValueError("valid sweep directions are 'forward', 'backward', and 'symmetric'")

    # Dinv for A*A.H
    Dinv = numpy.ravel(get_diagonal(A, norm_eq=2, inv=True))
    
    for i in range(iterations):
        amg_core.kaczmarz_gauss_seidel(A.indptr, A.indices, A.data,
                                           x, b, row_start,
                                           row_stop, row_step, Dinv)

#from pyamg.utils import dispatcher
#dispatch = dispatcher( dict([ (fn,eval(fn)) for fn in __all__ ]) )
