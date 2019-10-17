"""
Metric Tensor and Derivatives of Basis Vectors.
"""

import sys
import copy
import itertools
from sympy import diff, trigsimp, Matrix, Rational, \
    sqf_list, Symbol, sqrt, eye, zeros, S, expand, Mul, \
    Add, simplify, together, ratsimp, Expr, latex, \
    Function

from . import printer
from . import utils

half = Rational(1, 2)

def apply_function_list(f,x):
    if isinstance(f,(tuple,list)):
        fx = x
        for fi in f:
            fx = fi(fx)
        return fx
    else:
        return f(x)

def str_to_lst(s):
    if '[' in s:
        s = s.replace('[', '')
    if ']' in s:
        s = s.replace(']', '')
    s_lst = s.split(',')
    v_lst = []
    for x in s_lst:
        try:
            v_lst.append(int(s))
        except ValueError:
            v_lst.append(Symbol(s, real=True))
    return v_lst


def linear_expand(expr, mode=True):

    if isinstance(expr, Expr):
        expr = expand(expr)
    if expr == 0:
        coefs = [expr]
        bases = [S(1)]
        return (coefs, bases)

    if isinstance(expr, Add):
        args = expr.args
    else:
        if expr.is_commutative:
            return ([expr], [S(1)])
        else:
            args = [expr]
    coefs = []
    bases = []
    for term in args:
        if term.is_commutative:
            if S(1) in bases:
                coefs[bases.index(S(1))] += term
            else:
                bases.append(S(1))
                coefs.append(term)
        else:
            c, nc = term.args_cnc()
            base = nc[0]
            coef = Mul._from_args(c)
            if base in bases:
                coefs[bases.index(base)] += coef
            else:
                bases.append(base)
                coefs.append(coef)
    if mode:
        return (coefs, bases)
    else:
        return list(zip(coefs, bases))

def collect(A, nc_list):
    """
    Parameters
    -----------
    A :
        a linear combination of noncommutative symbols with scalar
        expressions as coefficients
    nc_list :
        noncommutative symbols in A to combine

    Returns
    -------
    sympy.Basic
        A sum of the terms containing the noncommutative symbols in `nc_list` such that no elements
        of `nc_list` appear more than once in the sum. All coefficients of a given element of `nc_list`
        are combined into a single coefficient.
    """
    (coefs,bases) = linear_expand(A)
    C = S(0)
    for x in nc_list:
        if x in bases:
            i = bases.index(x)
            C += coefs[i]*x
    return C


def square_root_of_expr(expr):
    """
    If expression is product of even powers then every power is divided
    by two and the product is returned.  If some terms in product are
    not even powers the sqrt of the absolute value of the expression is
    returned.  If the expression is a number the sqrt of the absolute
    value of the number is returned.
    """
    if expr.is_number:
        if expr > 0:
            return(sqrt(expr))
        else:
            return(sqrt(-expr))
    else:
        expr = trigsimp(expr)
        (coef, pow_lst) = sqf_list(expr)
        if coef != S(1):
            if coef.is_number:
                coef = square_root_of_expr(coef)
            else:
                coef = sqrt(abs(coef))  # Product coefficient not a number
        for p in pow_lst:
            (f, n) = p
            if n % 2 != 0:
                return(sqrt(abs(expr)))  # Product not all even powers
            else:
                coef *= f ** (n / 2)  # Positive sqrt of the square of an expression
        return coef


def symbols_list(s, indices=None, sub=True, commutative=False):

    if isinstance(s, list):  # s is already a list of symbols
        return(s)

    if sub is True:  # subscripted list
        pos = '_'
    else:  # superscripted list
        pos = '__'

    if indices is None:  # symbol list completely generated by s
        if '*' in s:
            [base, index] = s.split('*')
            if '|' in s:
                index = index.split('|')
                s_lst = [base + pos + i for i in index]
            else:  # symbol list indexed with integers 0 to n-1
                try:
                    n = int(index)
                except ValueError:
                    raise ValueError(index + 'is not an integer')
                s_lst = [base + pos + str(i) for i in range(n)]
        else:
            if ',' in s:
                s_lst = s.split(',')
            else:
                s_lst = s.split(' ')
            if not sub:
                s_lst = [x.replace('_', '__', 1) for x in s_lst]

    else:  # indices symbol list used for sub/superscripts of generated symbol list
        s_lst = [s + pos + str(i) for i in indices]
    return [Symbol(printer.Eprint.Base(s), commutative=commutative) for s in s_lst]


def test_init_slots(init_slots, **kwargs):
    """
    Tests kwargs for allowed keyword arguments as defined by dictionary
    init_slots.  If keyword argument defined by init_slots is not present
    set default value asdefined by init_slots.  Allow for backward
    compatible keyword arguments by equivalencing keywords by setting
    default value of backward compatible keyword to new keyword and then
    referencing new keywork (see init_slots for Metric class and equivalence
    between keywords 'g' and 'metric')
    """

    for slot in kwargs:
        if slot not in init_slots:
            print('Allowed keyed input arguments')
            for key in init_slots:
                print(key + ': ' + init_slots[key][1])
            raise ValueError('"' + slot + ' = " not in allowed values.')
    for slot in init_slots:
        if slot in kwargs:
            if init_slots[slot][0] in init_slots:  # redirect for backward compatibility
                kwargs[init_slots[slot][0]] = kwargs[slot]
        else:  # use default value
            if init_slots[slot][0] in init_slots:  # redirect for backward compatibility
                kwargs[init_slots[slot][0]] = init_slots[init_slots[slot][0]][0]
            kwargs[slot] = init_slots[slot][0]
    return kwargs


class Simp:
    modes = [simplify]

    @staticmethod
    def profile(s):
        Simp.modes = s
        return

    @staticmethod
    def apply(expr):
        (coefs, bases) = linear_expand(expr)
        obj = S(0)
        if isinstance(Simp.modes, list) or isinstance(Simp.modes, tuple):
            for (coef, base) in zip(coefs, bases):
                for mode in Simp.modes:
                    coef = mode(coef)
                obj += coef * base
        else:
            for (coef, base) in zip(coefs, bases):
                obj += Simp.modes(coef) * base
        return obj

    @staticmethod
    def applymv(mv):
        mv.obj = Simp.apply(mv.obj)
        return mv


class Metric(object):

    """
    Data Variables -

        g[,]: metric tensor (sympy matrix)
        g_inv[,]: inverse of metric tensor (sympy matirx)
        norm: normalized diagonal metric tensor (list of sympy numbers)
        coords[]: coordinate variables (list of sympy symbols)
        is_ortho: True if basis is orthogonal (bool)
        connect_flg: True if connection is non-zero (bool)
        basis[]: basis vector symbols (list of non-commutative sympy variables)
        r_symbols[]: reciprocal basis vector symbols (list of non-commutative sympy variables)
        n: dimension of vector space/manifold (integer)
        n_range: list of basis indices
        de[][]: derivatives of basis functions.  Two dimensional list. First
                entry is differentiating coordiate. Second entry is basis
                vector.  Quantities are linear combinations of basis vector
                symbols.
        sig: Signature of metric (p,q) where n = p+q.  If metric tensor
             is numerical and orthogonal it is calculated.  Otherwise the
             following inputs are used -

             input   signature                Type
              "e"      (n,0)    Euclidean
              "m+"     (n-1,1)  Minkowski (One negative square)
              "m-"     (1,n-1)  Minkowski (One positive square)
               p       (p,n-p)  General (integer not string input)
    """

    count = 1

    init_slots = {'g': (None, 'metric tensor'),
                  'coords': (None, 'manifold/vector space coordinate list/tuple'),
                  'X': (None, 'vector manifold function'),
                  'norm': (False, 'True to normalize basis vectors'),
                  'debug': (False, 'True to print out debugging information'),
                  'gsym': (None, 'String s to use "det("+s+")" function in reciprocal basis'),
                  'sig': ('e', 'Signature of metric, default is (n,0) a Euclidean metric'),
                  'Isq': ('-', "Sign of square of pseudo-scalar, default is '-'"),
                  'wedge': (True, 'Use ^ symbol to print basis blades')}

    @staticmethod
    def dot_orthogonal(V1, V2, g=None):
        """
        Returns the dot product of two vectors in an orthogonal coordinate
        system.  V1 and V2 are lists of sympy expressions.  g is
        a list of constants that gives the signature of the vector space to
        allow for non-euclidian vector spaces.

        This function is only used to form the dot product of vectors in the
        embedding space of a vector manifold or in the case where the basis
        vectors are explicitly defined by vector fields in the embedding
        space.

        A g of None is for a Euclidian embedding space.
        """
        if g is None:
            dot = 0
            for (v1, v2) in zip(V1, V2):
                dot += v1 * v2
            return dot
        else:
            if len(g) == len(V1):
                dot = 0
                for (v1, v2, gii) in zip(V1, V2, g):
                    dot += v1 * v2 * gii
                return dot
            else:
                raise ValueError('In dot_orthogonal dimension of metric ' +
                                 'must equal dimension of vector')

    def metric_symbols_list(self, s=None):  # input metric tensor as string
        """
        rows of metric tensor are separated by "," and elements
        of each row separated by " ".  If the input is a single
        row it is assummed that the metric tensor is diagonal.

        Output is a square matrix.
        """
        if s is None:
            s = self.n * '# '
            s = self.n * (s[:-1] + ',')
            s = s[:-1]

        if utils.isstr(s):
            rows = s.split(',')
            n_rows = len(rows)

            if n_rows == 1:  # orthogonal metric
                m_lst = s.split(' ')
                m = []
                for (s, base) in zip(m_lst, self.basis):
                    if s == '#':
                        s_symbol = Symbol('(' + str(base) + '.' + str(base) + ')', real=True)
                    else:
                        if '/' in s:
                            [num, dem] = s.split('/')
                            s_symbol = Rational(num, dem)
                        else:
                            s_symbol = Rational(s)
                    m.append(s_symbol)

                if len(m) != self.n:
                    raise ValueError('Input metric "' + s + '" has' +
                                     ' different rank than bases "' + str(self.basis) + '"')
                diagonal = eye(self.n)

                for i in self.n_range:
                    diagonal[i, i] = m[i]
                return diagonal

            else:  # non orthogonal metric
                rows = s.split(',')
                n_rows = len(rows)
                m_lst = []
                for row in rows:
                    cols = row.strip().split(' ')
                    n_cols = len(cols)
                    if n_rows != n_cols:  # non square metric
                        raise ValueError("'" + s + "' does not represent square metric")
                    m_lst.append(cols)
                m = []
                n = len(m_lst)
                if n != self.n:
                    raise ValueError('Input metric "' + s + '" has' +
                                     ' different rank than bases "' + str(self.basis) + '"')
                n_range = list(range(n))
                for (row, i1) in zip(m_lst, n_range):
                    row_symbols = []
                    for (s, i2) in zip(row, n_range):
                        if s == '#':
                            if i1 <= i2:  # for default elment insure symmetry
                                row_symbols.append(Symbol('(' + str(self.basis[i1]) +
                                                          '.' + str(self.basis[i2]) + ')', real=True))
                            else:
                                row_symbols.append(Symbol('(' + str(self.basis[i2]) +
                                                          '.' + str(self.basis[i1]) + ')', real=True))
                        else:
                            if '/' in s:  # element is fraction
                                [num, dem] = s.split('/')
                                row_symbols.append(Rational(num, dem))
                            else:  # element is integer
                                row_symbols.append(Rational(s))
                    m.append(row_symbols)
                m = Matrix(m)
                return m

    def derivatives_of_g(self):
        # dg[i][j][k] = \partial_{x_{k}}g_{ij}

        dg = [[[
            diff(self.g[i, j], x_k)
            for x_k in self.coords]
            for j in self.n_range]
            for i in self.n_range]

        return dg

    def init_connect_flg(self):
        # See if metric is flat

        self.connect_flg = False

        for i in self.n_range:
            for j in self.n_range:
                for k in self.n_range:
                    if self.dg[i][j][k] != 0:
                        self.connect_flg = True
                        break

    def derivatives_of_basis(self):  # Derivatives of basis vectors from Christoffel symbols

        n_range = self.n_range

        self.dg = dg = self.derivatives_of_g()

        self.init_connect_flg()

        if not self.connect_flg:
            self.de = None
            return

        de = []  # de[i][j] = \partial_{x_{i}}e^{x_{j}}

        # Christoffel symbols of the first kind, \Gamma_{ijk}
        # TODO handle None
        dG = self.Christoffel_symbols(mode=1)

        # \frac{\partial e_{j}}{\partial x^{i}} = \Gamma_{ijk} e^{k}
        de = [[
            sum([Gamma_ijk * e__k for (Gamma_ijk, e__k) in zip(dG[i][j], self.r_symbols)])
            for j in n_range]
        for i in n_range]

        if self.debug:
            printer.oprint('D_{i}e^{j}', de)
        self.de = de
        return

    def inverse_metric(self):

        if self.g_inv is not None:
            return

        if self.is_ortho:  # Orthogonal metric
            self.g_inv = eye(self.n)
            for i in range(self.n):
                self.g_inv[i,i] = S(1)/self.g(i,i)
        else:
            if self.gsym is None:
                self.g_inv = simplify(self.g.inv())
            else:
                self.detg = Function('|' +self.gsym +'|',real=True)(*self.coords)
                self.g_adj = simplify(self.g.adjugate())
                self.g_inv = self.g_adj/self.detg
        return

    def Christoffel_symbols(self,mode=1):
        """
        mode = 1  Christoffel symbols of the first kind
        mode = 2  Christoffel symbols of the second kind
        """

        # See if connection is zero
        if not self.connect_flg:
            return

        n_range = self.n_range

        # dg[i][j][k] = \partial_{x_{k}}g_{ij}
        dg = self.dg

        if mode == 1:

            dG = []  # dG[i][j][k] = half * (dg[j][k][i] + dg[i][k][j] - dg[i][j][k])

            # Christoffel symbols of the first kind, \Gamma_{ijk}
            # \partial_{x^{i}}e_{j} = \Gamma_{ijk}e^{k}

            def Gamma_ijk(i, j, k):
                return half * (dg[j][k][i] + dg[i][k][j] - dg[i][j][k])

            dG = [[[
                Simp.apply(Gamma_ijk(i, j, k))
                for k in n_range]
                for j in n_range]
                for i in n_range]

            if self.debug:
                printer.oprint('Gamma_{ijk}', dG)
            return dG

        elif mode == 2:
            # TODO handle None
            Gamma1 = self.Christoffel_symbols(mode=1)

            self.inverse_metric()

            # Christoffel symbols of the second kind, \Gamma_{ij}^{k} = \Gamma_{ijl}g^{lk}
            # \partial_{x^{i}}e_{j} = \Gamma_{ij}^{k}e_{k}

            def Gamma2_ijk(i, j, k):
                return sum([Gamma_ijl * self.g_inv[l, k] for l, Gamma_ijl in enumerate(Gamma1[i][j])])

            Gamma2 = [[[
                Simp.apply(Gamma2_ijk(i, j, k))
                for k in n_range]
                for j in n_range]
                for i in n_range]

            return Gamma2
        else:
            raise ValueError('In Christoffle_symobols mode = ' + str(mode) +' is not allowed\n')

    def normalize_metric(self):

        if self.de is None:
            return

        renorm = []
        #  Generate mapping for renormalizing reciprocal basis vectors
        for ib in self.n_range:  # e^{ib} --> e^{ib}/|e_{ib}|
            renorm.append((self.r_symbols[ib], self.r_symbols[ib] / self.e_norm[ib]))

        # Normalize derivatives of basis vectors

        for x_i in self.n_range:
            for jb in self.n_range:
                self.de[x_i][jb] = Simp.apply((((self.de[x_i][jb].subs(renorm)
                                              - diff(self.e_norm[jb], self.coords[x_i]) *
                                              self.basis[jb]) / self.e_norm[jb])))
        if self.debug:
            for x_i in self.n_range:
                for jb in self.n_range:
                    print(r'\partial_{' + str(self.coords[x_i]) + r'}\hat{e}_{' + str(self.coords[jb]) + '} =', self.de[x_i][jb])

        # Normalize metric tensor

        for ib in self.n_range:
            for jb in self.n_range:
                self.g[ib, jb] = Simp.apply(self.g[ib, jb] / (self.e_norm[ib] * self.e_norm[jb]))

        if self.debug:
            printer.oprint('e^{i}->e^{i}/|e_{i}|', renorm)
            printer.oprint('renorm(g)', self.g)

        return

    def signature(self):
        if self.is_ortho:
            p = 0
            q = 0
            for i in self.n_range:
                g_ii = self.g[i,i]
                if g_ii.is_number:
                    if g_ii > 0:
                        p += 1
                    else:
                        q += 1
                else:
                    break
            if p + q == self.n:
                self.sig = (p,q)
                return
        if isinstance(self.sig,int):  # General signature
            if self.sig <= self.n:
                self.sig = (self.sig,self.n - self.sig)
                return
            else:
                raise ValueError('self.sig = ' + str(self.sig) + ' > self.n, not an allowed hint')
        if utils.isstr(self.sig):
            if self.sig == 'e':  # Euclidean metric signature
                self.sig = (self.n, 0)
            elif self.sig == 'm+':  # Minkowski metric signature (n-1,1)
                self.sig = (self.n - 1, 1)
            elif self.sig == 'm-':  # Minkowski metric signature (1,n-1)
                self.sig = (1, self.n - 1)
            else:
                raise ValueError('self.sig = ' + str(self.sig) + ' is not an allowed hint')
            return
        raise ValueError(str(self.sig) + ' is not allowed value for self.sig')


    def __init__(self, basis, **kwargs):

        kwargs = test_init_slots(Metric.init_slots, **kwargs)

        self.name = 'GA' + str(Metric.count)
        Metric.count += 1

        if not utils.isstr(basis):
            raise TypeError('"' + str(basis) + '" must be string')

        X = kwargs['X']  # Vector manifold
        g = kwargs['g']  # Explicit metric or base metric for vector manifold
        debug = kwargs['debug']
        coords = kwargs['coords']  # Manifold coordinates (sympy symbols)
        norm = kwargs['norm']  # Normalize basis vectors
        self.sig = kwargs['sig']  # Hint for metric signature
        """
        String for symbolic metric determinant.  If self.gsym = 'g'
        then det(g) is sympy scalar function of coordinates with
        name 'det(g)'.  Useful for complex non-orthogonal coordinate
        systems or for calculations with general metric.
        """
        self.gsym = kwargs['gsym']
        self.Isq = kwargs['Isq']  # Sign of I**2, only needed if I**2 not a number

        self.debug = debug
        self.is_ortho = False  # Is basis othogonal
        self.coords = coords  # Manifold coordinates
        if self.coords is None:
            self.connect_flg = False
        else:
            self.connect_flg = True  # Connection needed for postion dependent metric
        self.norm = norm  # True to normalize basis vectors
        self.detg = None  # Determinant of g
        self.g_adj = None  # Adjugate of g
        self.g_inv = None  # Inverse of g
        # Generate list of basis vectors and reciprocal basis vectors
        # as non-commutative symbols

        if ' ' in basis or ',' in basis or '*' in basis:  # bases defined by substrings separated by spaces or commas
            self.basis = symbols_list(basis)
            self.r_symbols = symbols_list(basis, sub=False)
        else:
            if coords is not None:  # basis defined by root string with symbol list as indices
                self.basis = symbols_list(basis, coords)
                self.r_symbols = symbols_list(basis, coords, sub=False)
                self.coords = coords
                if self.debug:
                    printer.oprint('x^{i}', self.coords)
            else:
                raise ValueError('for basis "' + basis + '" coords must be entered')

        if self.debug:
            printer.oprint('e_{i}', self.basis, 'e^{i}', self.r_symbols)
        self.n = len(self.basis)
        self.n_range = list(range(self.n))

        # Generate metric as list of lists of symbols, rationals, or functions of coordinates

        if g is None:
            if X is None:  # default metric from dot product of basis as symbols
                self.g = self.metric_symbols_list()
            else:  # Vector manifold
                if coords is None:
                    raise ValueError('For metric derived from vector field ' +
                                     ' coordinates must be defined.')
                else:  # Vector manifold defined by vector field
                    dX = []
                    for coord in coords:  # Get basis vectors by differentiating vector field
                        dX.append([diff(x, coord) for x in X])
                    g_tmp = []
                    for dx1 in dX:
                        g_row = []
                        for dx2 in dX:
                            dx1_dot_dx2 = trigsimp(Metric.dot_orthogonal(dx1, dx2, g))
                            g_row.append(dx1_dot_dx2)
                        g_tmp.append(g_row)
                    self.g = Matrix(g_tmp)
                    if self.debug:
                        printer.oprint('X_{i}', X, 'D_{i}X_{j}', dX)

        else:  # metric is symbolic or list of lists of functions of coordinates
            if utils.isstr(g):  # metric elements are symbols or constants
                if g == 'g':  # general symbolic metric tensor (g_ij functions of position)
                    g_lst = []
                    g_inv_lst = []
                    for coord in self.coords:
                        i1 = str(coord)
                        tmp = []
                        tmp_inv = []
                        for coord2 in self.coords:
                            i2 = str(coord2)
                            tmp.append(Function('g_'+i1+'_'+i2)(*self.coords))
                            tmp_inv.append(Function('g__'+i1+'__'+i2)(*self.coords))
                        g_lst.append(tmp)
                        g_inv_lst.append(tmp_inv)
                    self.g = Matrix(g_lst)
                    self.g_inv = Matrix(g_inv_lst)
                else:  # specific symbolic metric tensor (g_ij are symbolic or numerical constants)
                    self.g = self.metric_symbols_list(g)  # construct symbolic metric from string and basis
            else:  # metric is given as list of function or list of lists of function or matrix of functions
                if isinstance(g, Matrix):
                    self.g = g
                else:
                    if isinstance(g[0], list):
                        self.g = Matrix(g)
                    else:
                        m = eye(len(g))
                        for i in range(len(g)):
                            m[i, i] = g[i]
                        self.g = m

        self.g_raw = copy.deepcopy(self.g)  # save original metric tensor for use with submanifolds

        if self.debug:
            printer.oprint('g', self.g)

        # Determine if metric is orthogonal

        self.is_ortho = True

        for i in self.n_range:
            for j in self.n_range:
                if i < j:
                    if self.g[i, j] != 0:
                        self.is_ortho = False
                        break

        self.g_is_numeric = True

        for i in self.n_range:
            for j in self.n_range:
                if i < j:
                    if not self.g[i, j].is_number:
                        self.g_is_numeric = False
                        break

        if self.coords is not None:
            self.derivatives_of_basis()  # calculate derivatives of basis
            if self.norm:  # normalize basis, metric, and derivatives of normalized basis
                if not self.is_ortho:
                    raise ValueError('!!!!Basis normalization only implemented for orthogonal basis!!!!')
                self.e_norm = []
                for i in self.n_range:
                    self.e_norm.append(square_root_of_expr(self.g[i, i]))
                if debug:
                    printer.oprint('|e_{i}|', self.e_norm)
            else:
                self.e_norm = None

        if self.norm:
            if self.is_ortho:
                self.normalize_metric()
            else:
                raise ValueError('!!!!Basis normalization only implemented for orthogonal basis!!!!')

        if not self.g_is_numeric:
            self.signature()
            # Sign of square of pseudo scalar
            self.e_sq_sgn = '+'
            if ((self.n*(self.n-1))//2+self.sig[1])%2 == 1:
                self.e_sq_sgn = '-'

        if self.debug:
            print('signature =', self.sig)


if __name__ == "__main__":
    pass

