"""
Print and plot functions for testing convergence and scalability.
"""
from numpy import array, random, mean, prod, zeros
from scipy import rand, log10

def print_cycle_history(resvec, ml, verbose=False, plotting=False):
    """
    Shows a summary of the complexity, convergence factors, and total work
    along with a verbose mode highlighited each iteration.

    Parameters
    ----------
    resvec : array like
        Vector of residuals from a MG iteration
    ml : multilevel
        Multilevel object from AMG setup
    verbose : {True, False}
        Indicates verbose text output
    plotting : {True, False}
        Plot the residual history

    Notes
    -----
        - Factor refers to the immediate reduction factor

        - A-mean refers to the current or running arithmetic mean

        - G-mean refers to the geometric mean (current or 

        - Work is the estimated total work needed to reduce the residual by a
            factor of 10, based on the geometric mean of the convergence factors
            and on the cycle complexity
    """
    resvec = array(resvec)
    factors = resvec[1:]/resvec[0:-1]

    print '---Convergence Summary---------------------------------------'
    print ''
    avg_convergence_factor = (resvec[-1]/resvec[0])**(1.0/len(resvec))
    print '             Levels: %d' % len(ml.levels)
    print '   Cycle Complexity: %6.3f' % ml.cycle_complexity()
    print 'Operator Complexity: %6.3f' % ml.operator_complexity()
    print '    Grid Complexity: %6.3f' % ml.grid_complexity()
    print 'avg geo conv factor: %6.3f' % avg_convergence_factor
    print '               work: %6.3f' % (-ml.cycle_complexity() / log10(avg_convergence_factor))
    print ''

    total_nnz =  sum([level.A.nnz for level in ml.levels])
    print 'level   unknowns     nnz'
    for n,level in enumerate(ml.levels):
        A = level.A
        print '   %-2d   %-10d   %-10d [%5.2f%%]' % (n,A.shape[1],A.nnz,(100*float(A.nnz)/float(total_nnz)))

    if(verbose):
        print ''
        print '---Convergence Summary (verbose)-----------------------------'
        print '%20s'%'Factors:'
        plist = ('iter', 'Factor', 'A-Mean','G-Mean', 'Work')
        print '%-10s %-10s %-10s %-10s %-10s' % plist

        for i in range(0,len(resvec)):
            if(i>0):
                iresvec = resvec[:(i+1)]                            # running list of residuals
                ifactors = iresvec[1:]/iresvec[0:-1]                # running list of factors

                ifactor = ifactors[-1]                              # current arith mean
                aafactor = mean(ifactors)                           # running arith mean
                gafactor = (iresvec[-1]/iresvec[0])**(1.0/(i+1))    # geo mean

                ocx = ml.cycle_complexity()
                iwork = - ocx / log10(gafactor)                        # current work-per-digit

                plist = (i, ifactor, aafactor, gafactor, iwork)
                print '%-10d %-10.3f %-10.3f %-10.3f %-10.3f' % plist
            else:
                print '%-10d' % (i)

    if(plotting):
        from pylab import plot, show, semilogy, figure, xlabel, ylabel, axis
        figure(1)
        semilogy(resvec,'k')
        xlabel('iteration')
        ylabel('residual')
        show()

def print_scalability(factors,complexity,nnz,nlist,plotting=False):
    """
    Shows a summary of the scalability in problems size n.

    Parameters
    ----------
    factors : array like
        Convergence factors for a list of problem sizes
    complexity : array like
        Complexities (cycle,operator,grid) for a list a problem sizes
    nnz : array like
        A list of the number of nonzeros in the matrix equations for each
        problem
    nlist : array like
        A list of problem sizes

    plotting : {True, False}
        Plot the residual history

    """
    print '---Scalability Summary---------------------------------------'
    print ''
    print '%-10s %-10s %-10s %-10s %-10s'%("n","nnz","rho","OpCx","Work")
    run=0
    work = zeros((len(nlist),1)).ravel()
    for n in nlist:
        work[run]=-complexity[run]/log10(factors[run]);
        if(run>0):
            str = (n,nnz[run],factors[run],complexity[run],work[run])
            print '%-10.3d %-10.3d %-10.3f %-10.3f %-10.3f'%str
        else:
            print '%-10.3d'%n
        run+=1

    if(plotting):
        from pylab import plot, show, semilogy, figure, xlabel, ylabel, axis
        figure(1)
        maxscale = max([work.max(),2])
        plot(nlist[1:],work[1:],'k')
        axis([nlist[1],nlist[-1],0,1.1*maxscale])
        xlabel('n')
        ylabel('work per digit of accuracy')
        show()