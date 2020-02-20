# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_data.core_pd.ipynb (unless otherwise specified).

__all__ = ['NormalizeTSMulti', 'concat_ts_list', 'make_test', 'make_test_pct', 'TSDataLoaders']

# Cell
from .load import *
from ..core import *
from fastcore.all import *
from fastcore.imports import *
from fastai2.basics import *
from fastai2.data.transforms import *
from fastai2.tabular.core import *
from .load_pd import *

# Cell
def _zeros_2_ones(o, eps=1e-8):
    o[o < eps] = 1
    return o


# Cell

class NormalizeTSMulti(ItemTransform):
    "Normalize the Time-Series."
    def __init__(self, verbose=False, make_ones=True, eps=1e-7, mean = None):
        """
        `make_ones` will make the std 1 if the std is smaller than `10*eps`.
        This is for blok seqences to not magnify the `y` part of the data.

        `mean` will set a mean instead of the mean of the x value.
        (
            TensorSeqs(x, label=[self.y_name + '_x'], m=['g']),
            TensorSeqs(tsx,label=self.ts_names),
            TensorCon(cat,label=self.cat_names).long(),
            TensorCon(con,label=self.con_names),
            TensorSeqs(y, label=[self.y_name+ '_y'], m=['r'])
        )
        """
        store_attr(self,'verbose, make_ones, eps, mean')
        self.m, self.s = {}, {}

    def encodes(self, o):
        for i in range(len(o)):
            if type(o[i]) == TensorCon and o[i].shape[-1]>0:
                self.m[i] = torch.mean(o[i])
                self.s[i] = _zeros_2_ones(o[i].std() +self.eps, self.eps*10)
            elif type(o[i]) == TensorSeqs:
                self.m[i] = torch.mean(o[i],-1,keepdim=True)
                self.s[i] = _zeros_2_ones( o[i].std(-1,keepdim=True) +self.eps, self.eps*10)
            else:
                print(f'{i} not found type {type(o[i])}')
                self.m[i], self.s[i] = 0, 1
        # y must be scaled with m
        # TODO make y its own type
        self.m[len(o)],self.s[len(o)] = self.m[0],self.s[0]
        if self.verbose:
            print('encodes',[a.shape for a in o],'m shape', {k:o.shape for k,o in self.m.items()},'s shape',{k:o.shape for k,o in self.s.items()})

        return Tuple([(o[i]-self.m[i])/self.s[i] for i in range(len(o))])

    def decodes(self, o):
        if o[0].is_cuda:
            self.m, self.s = to_device(self.m,'cuda'), to_device(self.s,'cuda')
            if sum([a.is_cuda for a in o]) != len(o):
                o = Tuple([to_device(a,'cuda') for a in o])
        else:
            if sum([a.is_cuda==False for a in o]) != len(o):
                o = Tuple([to_cpu(a) for a in o])
            self.m, self.s = to_cpu(self.m), to_cpu(self.s)
        if self.verbose:
            print('decodes',[a.shape for a in o], 'shape m/s',self.m.shape)
        return Tuple([(o[i]*self.s[i])+self.m[i] for i in range(len(o))])

# Cell
def concat_ts_list(train, val):
    items=L()
    assert len(train) == len(val)
    for t, v in zip(train, val):
        items.append(np.concatenate([t,v],1))
    return items

# Cell
def make_test(items:L(), horizon:int, lookback:int, keep_lookback:bool = False):
    """Splits the every ts in `items` based on `horizon + lookback`*, where the last part will go into `val` and the first in `train`.

    *if `keep_lookback`:
        it will only remove `horizon` from `train` otherwise also lookback.
    """
    train, val = L(), L()
    for ts in items:
        val.append(ts[:, -(horizon+lookback):])
        if keep_lookback:
            train.append(ts[:, :-(horizon)])
        else:
            train.append(ts[:, :-(horizon+lookback)])

    return train, val

def make_test_pct(items:L(), pct:float):
    """Splits the every ts in `items` based on `pct`(percentage) of the length of the timeserie, where the last part will go into `val` and the first in `train`.

    """
    train, val = L(), L()
    for ts in items:
        split_idx = int((1-pct)*ts.shape[1])
        train.append(ts[:,:split_idx])
        val.append(ts[:,split_idx:])

    return train, val

# Cell
class TSDataLoaders(DataLoaders):
    @classmethod
    @delegates(TSDataLoader.__init__)
    def from_folder(cls, data_path:Path, valid_pct=.5, seed=None, horizon=None, lookback=None, step=1,
                   nrows=None, skiprows=None, incl_test = True, path:Path='.', device=None, norm=True, **kwargs):
        """Create from M-compition style in `path` with `train`,`test` csv-files.

        The `DataLoader` for the test set will be save as an attribute under `test`
        """
        train, test = get_ts_files(data_path, nrows=nrows, skiprows=skiprows)
        items = concat_ts_list(train, test).map(tensor)
        horizon = ifnone(horizon, len(test[0]))
        lookback = ifnone(lookback, horizon * 3)
        return cls.from_items(items, horizon, lookback = lookback,  step = step, incl_test=incl_test, path=path, device=device, norm= norm,**kwargs)


    @classmethod
    @delegates(TSDataLoader.__init__)
    def from_items(cls, items:L, horizon:int, valid_pct=1.5, seed=None, lookback=None, step=1,
                   incl_test = True, path:Path='.', device=None, norm=True, **kwargs):
        """Create an list of time series.

        The `DataLoader` for the test set will be save as an attribute under `test`
        """
        if len(items[0].shape)==1:
            items = [i[None,:] for i in items]
        print(items[0].shape)
        lookback = ifnone(lookback, horizon * 4)
        device = ifnone(device, default_device())
        if incl_test:
            items, test = make_test(items, horizon, lookback, keep_lookback = True)
        train, valid = make_test(items, horizon + int(valid_pct*horizon), lookback , keep_lookback = True)
        if norm and 'after_batch' not in kwargs:
            make_ones = kwargs.pop('make_ones', True)
            kwargs.update({'after_batch':L(NormalizeTS(make_ones=make_ones))})
        db = DataLoaders(*[TSDataLoader(items, horizon=horizon, lookback=lookback, step=step, device=device, norm = False, **kwargs)
                           for items in [train,valid]], path=path, device=device)
        if incl_test:
            db.test = TSDataLoader(test, horizon=horizon, lookback=lookback, step=step, name='test', device=device, **kwargs)

            print(f"Train:{db.train.n}; Valid: {db.valid.n}; Test {db.test.n}")
        else:
            print(f"Train:{db.train.n}; Valid: {db.valid.n}")

        return db