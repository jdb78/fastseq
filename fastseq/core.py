# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_core.ipynb (unless otherwise specified).

__all__ = ['git_add', 'first_item', 'unpack_list', 'reverse_lst', 'concat_dct', 'multithread_f', 'pad_zeros', 'Skip',
           'get_ts_files', 'IndexsSplitter', 'TSeries', 'no_emp_dim', 'TensorSeq', 'TensorCon', 'TensorCat',
           'count_nested_lists', 'CatSeq', 'MultiTuple', 'get_ax', 'show_mt', 'ts_lists']

# Cell
from fastcore.all import *
from fastai2.basics import *
from typing import List
import pandas as pd
import numpy as np

# Cell
import shutil
def _copy(self, target):
    assert self.is_file()
    shutil.copy(str(self), str(target))  # str() only there for Python < (3, 6)

Path.copy = _copy

import shutil
def _del(path):
    shutil.rmtree(path, ignore_errors=True)

Path.delete = _del

# Cell
from git import Repo
from nbdev.export import Config as nb_Config
from nbdev.export import *

def git_add(fname, commit_msg='.'):
    repo = Repo(nb_Config().nbs_path.parent)
    notebook2script(fname)
    nb = read_nb(fname)
    default = find_default_export(nb['cells'])
    py = [os.path.join(nb_Config().lib_path,*default.split('.'))+'.py',
          os.path.join(nb_Config().nbs_path,fname)
         ]
    repo.index.add(py)
    repo.index.commit(commit_msg)
    return py


# Cell
def first_item(lst):
    if type(lst)==list or type(lst) == L:
        return lst[0]
    return lst

# Cell
def unpack_list(o, r=None):
    r = ifnone(r,L())
    for a in o:
        if isinstance(a,list) or isinstance(a,L):
            r = unpack_list(a, r)
        else:
            r.append(a)
    return r

# Cell
def reverse_lst(lst):
    return [[a for a in o] for o in list(np.array(lst).T)]


# Cell
def concat_dct(new_dct, expand_dct):
    """Concatanates `torch.tensor`'s in `new_dct` to the same `key` in expand_dct'."""
    for k,v in new_dct.items():
        if isinstance(v,torch.Tensor):
            if k in expand_dct:
                expand_dct[k] = torch.cat([expand_dct[k],v], axis = 0)
            else:
                expand_dct[k] = v
        else:
            if k in expand_dct:
                expand_dct[k] = concat_dct(new_dct[k], expand_dct[k])
            else:
                expand_dct[k] = concat_dct(new_dct[k], {})

    return expand_dct

# Cell
from multiprocessing.dummy import Pool as ThreadPool
def multithread_f(f, o:list, num_workers = None):
    pool = ThreadPool(num_workers)
    return pool.map(f, o)

# Cell
def pad_zeros(X, lenght):
    return  np.pad(
                X,
                pad_width=((0, 0), (lenght - X.shape[-1], 0)),
                mode='constant',
                constant_values=0
            )

# Cell
def Skip(percentage_remove):
    """Helper function for `pd.read_csv` and will randomly not load `percentage_remove`% of the whole dataset """

    def skip(x):
        if (np.random.rand() < percentage_remove or x == 0):
            return False
        return True
    return skip

# Cell
# TODO skip will skip different rows for train and val

def get_ts_files(path, recurse=True, folders=None, **kwargs):
    "Get image files in `path` recursively, only in `folders`, if specified."
    items = []
    for f in get_files(path, extensions=['.csv'], recurse=recurse, folders=folders):
        df = pd.read_csv(f, **kwargs)
        items.append(ts_lists(df.iloc[:, 1:].values))
    return items

# Cell
def IndexsSplitter(train_idx, val_idx=None, test=None):
    """Split `items` from 0 to `train_idx` in the training set, from `train_idx` to `val_idx` (or the end) in the validation set.

    Optionly if `test` will  in test set will also make test from val_idx to end.
    """
    _val_idx = ifnone(val_idx,-1)
    do_test = ifnone(test, False)
    def _inner(items, **kwargs):
        if _val_idx == -1:
            val_idx = len(items)
        else:
            val_idx = _val_idx
        train = L(np.arange(0, train_idx), use_list=True)
        valid = L(np.arange(train_idx, val_idx), use_list=True)
        if do_test:
            test = L(np.arange(val_idx,len(items)), use_list=True)
            return train, valid, test
        if not val_idx == len(items):
            warnings.warn("You lose data")
        return train, valid
    return _inner

# Cell
class TSeries(TensorBase):pass

def no_emp_dim(x):
    if len(x.shape)==1 :
        x = x[None,:]
    return np.vstack(x)


# Cell
import matplotlib.colors as mcolors
_colors = [v for k,v in mcolors.TABLEAU_COLORS.items()]
_colors += [v for k,v in mcolors.TABLEAU_COLORS.items()]# could be done better but ...
class TensorSeq(TSeries):
    def __new__(cls, x, **kwargs):
        res = tensor(x)
        res.__class__ = TensorSeq
        res._meta = kwargs
        return res

    def show(self, ax = None, ctx=None, **kwargs):
        ctx = ifnone(ctx, ax)
        if ctx is None: _, ctx = plt.subplots(figsize=(5,5))
        array = np.array(self.cpu())
        arrays = no_emp_dim(array)
        m = L(self._meta.get('m',_colors[:len(arrays)]))
        labels = L(self._meta.get('label',['x']*len(arrays)))
        if arrays.shape[-1] == 0:
            if len(labels):
                ctx.set_title(ctx.title._text +f"{labels} is empty")
            return ctx
        assert len(m)==len(labels)==len(arrays),f"{len(m)}=={len(labels)}=={len(arrays)}"
        t = np.arange(array.shape[-1])
        for a, c, label in zip(arrays, m, labels):
            ls = ('-',None) if 'y' not in label else ('None','*' )
            ctx.plot(t, a, ls = ls[0], marker = ls[1], c=c,
                     **kwargs, label=label)
        ctx.legend()
        return ctx

# Cell
def _get_its_shape(o):
    if len(o.shape) == 0: return 1, o[None]
    return len(o), o


class TensorCon(TSeries):
    _name = 'Constant'
    def show(self, ax = None, ctx=None):
        ax = ifnone(ax,ctx)
        if ax is None:
            _, ax = plt.subplots(figsize=(5,5))
        l, its = _get_its_shape(self)
        dct = {k:np.round(its[i].item(),2) for k,i in zip(L(self._meta.get('label',self._name)),range(l))}
        if dct == {}:
            dct = ''
        ax.set_title(ax.title._text +f"{dct}")
        return ax

# Cell
def _shape(lst):
    def ishape(lst):
        shapes = [ishape(x) if isinstance(x, list) else [] for x in lst]
        shape = shapes[0]
        if shapes.count(shape) != len(lst):
            raise ValueError('Ragged list')
        shape.append(len(lst))
        return shape
    return tuple(reversed(ishape(lst)))

class TensorCat():
    _name = 'Catagory'
    def __init__(self, o, label = None):
        if isinstance(o, TensorCat):
            o, label = o.o, o._meta['label']
        assert label is not None, f"label is not optional"
        self.o = L(o)
        self._meta ={'label': label}
        self.k2i = {k:i for i,k in enumerate(self._meta['label'])}
        self.shape = _shape(self.o)

    def _dct(self):
        return {k:v for k,v in zip(self._meta['label'], self.o)}

    def __repr__(self):
        return f"TensorCat({list(self.o)}, label = {list(self._meta['label'])})"

    def __eq__(self, o):
        if isinstance(o, TensorCat):
            return self.o == self.o
        return False

    def show(self, ax = None, ctx=None):
        ax = ifnone(ax,ctx)
        if ax is None:
            _, ax = plt.subplots(figsize=(5,5))
        dct = self._dct()
        if dct == {}:
            dct = ''
        ax.set_title(ax.title._text +f"{dct}")
        return ax



# Cell
def count_nested_lists(lst, r = 0):
    """Counts the number of lists inside a list. Note it will only look at the first item."""
    if type(lst) == list:
        r += 1
        if type(lst[0]) == list:
            return count_nested_lists(lst[0], r)
    return r

# Cell
class CatSeq(TensorCat):
    def __init__(self, o:List[List[str]], label, **kwargs):
        if isinstance(o, CatSeq):
            o, label = o.o, o._meta['label']
#         l = count_nested_lists(o)
        self.o = o
        self._meta ={'label': label, **kwargs}
        self.shape = np.array(o).shape
#         assert len(self.shape) == 2, f"shape of input in CatSeq not the correct size {self.o}"

    def _dct(self):
        return {k:v for k,v in zip(self._meta['label'],self.o)}

    def __repr__(self):
        return f"CatSeq({list(self.o)}, label = {list(self._meta['label'])})"

    def __eq__(self, o):
        if isinstance(o, TensorCat):
            return self.o == self.o
        return False

    def __iter__(self):
        for i in range(self.shape[0]):
            yield list(self.o[i])

    def dict(self):
        return {k:v for k,v in zip(self._meta['label'], self.o)}

    def show(self, ax = None, ctx=None):
        ax = ifnone(ax,ctx)
        if ax is None:
            _, ax = plt.subplots(figsize=(5,5))
        lst =  '\n'.join(self._dct().keys())

        if lst == '':
            lst = ''
        elif len(self._dct()) == 1:
            lst = 'CatSeq:\n' +lst
        else:
            lst = 'CatSeqs:\n' +lst
        ax.text(0.01, 0.99, lst,
        verticalalignment='top', horizontalalignment='left',
        transform=ax.transAxes,
        color=self._meta.get('color','green'), fontsize=self._meta.get('fontsize',10))
        return ax

# Cell
class MultiTuple(Tuple):
    """The same as `Tuple` only stores the types in `_types` and if _meta stores those in `_meta`"""
    def __new__(cls, x, *rest, **kwargs):
        r = Tuple.__new__(cls,x, *rest)
        r._meta = {i:a._meta for i,a in enumerate(L(r)) if hasattr(a,'_meta')}
        r._types = [type(a) for a in L(r)]
        return r

# Cell
from fastai2.vision.data import get_grid
def _show_multituple(t, ax):
    for o in t:
        ax = o.show(ctx = ax)
    return ax

def get_ax(ax, ctx, figsize, **kwargs):
    ax = ifnone(ax,ctx)
    if ax is None:
        _, ax = plt.subplots(figsize=figsize, **kwargs)
    return ax

@delegates(plt.subplots)
def show_mt(self, ax = None, ctx=None, figsize = (10,10), **kwargs):
    ax = get_ax(ax, ctx, figsize, **kwargs)
    return _show_multituple(self, ax)
MultiTuple.show = show_mt

# Cell
def ts_lists(ts:np.ndarray)-> L:
    """Transforms a `np.ndarray` of shape (timeseries, max_time) to a list of timeseries with shape (1,time).

    where:

    max_time = the length of the longest timeserie

    time = the length of the non-nan values of that specific timeserie
    """
    lst = L()
    for time_series in ts:
        lst.append(time_series[~np.isnan(time_series)][None,:])
    return lst