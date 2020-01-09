# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_data.load.ipynb (unless otherwise specified).

__all__ = ['pad_zeros', 'TSTensorSeq', 'TSTensorSeqy', 'TSTensorSeqyCreate', 'TSDataLoader', 'get_ts_files',
           'concat_ts_list', 'sep_last', 'IndexsSplitter', 'TSBlock', 'TSDataBunch']

# Cell
from ..core import *
from .external import *
from fastcore.utils import *
from fastcore.imports import *
from fastai2.basics import *
from fastai2.tabular.core import *
from .transforms import *

# Cell
import numpy as np
import pandas as pd
from torch.utils.data import Dataset, DataLoader

# Cell
def pad_zeros(X, lenght):
    return  np.pad(
                X,
                pad_width=((0, 0), (lenght - X.shape[-1], 0)),
                mode='constant',
                constant_values=0
            )

# Cell
class TSTensorSeq(TensorSeq): pass
class TSTensorSeqy(TensorSeq):

    @classmethod
    def create(cls, t)->None:
        "Convert an array or a list of points `t` to a `Tensor`"
        return cls(tensor(t).view(-1, 1).float())

    def show(self, ctx=None, **kwargs):
        if 'figsize' in kwargs:
            del kwargs['figsize']
        array = np.array(self.cpu())
        array = no_emp_dim(array)
        x_len = self._meta.get('x_len',0)
        m = self._meta.get('m','-*r')
        ctx.plot(np.arange(x_len,x_len+len(array)), array, m, **kwargs)
        return ctx

# Cell
TSTensorSeqyCreate = Transform(TSTensorSeqy.create)
TSTensorSeqyCreate.loss_func = MSELossFlat()
TSTensorSeqy.create = TSTensorSeqyCreate

# Cell
# TODO maybe incl. start where the last one ended and therefor keep hidden state
@delegates()
class TSDataLoader(TfmdDL):
    def __init__(self, time_series, horizon, lookback=72, step=1, bs=64,  num_workers=0, **kwargs):
        self.items, self.horizon, self.lookback, self.step = time_series, horizon, lookback, step
        self.make_ids()
        super().__init__(dataset=time_series, bs=bs, num_workers=num_workers, **kwargs)

    def make_ids(self):
        # Slice each time series into examples, assigning IDs to each
        last_id = 0
        n_dropped = 0
        self._ids = {}
        for i, ts in enumerate(self.items):
            if isinstance(ts,tuple):
                ts = ts[0] # no idea why they become tuples
            num_examples = (ts.shape[-1] - self.lookback - self.horizon + self.step) // self.step
            # Time series shorter than the forecast horizon need to be dropped.
            if ts.shape[-1] < self.horizon:
                n_dropped += 1
                continue
            # For short time series zero pad the input
            if ts.shape[-1] < self.lookback + self.horizon:
                num_examples = 1
            for j in range(num_examples):
                self._ids[last_id + j] = (i, j * self.step)
            last_id += num_examples

            # Inform user about time series that were too short
        if n_dropped > 0:
            print("Dropped {}/{} time series due to length.".format(
                    n_dropped, len(self.items)))
        # Store the number of training examples
        self.n = int(self._ids.__len__() )

    def get_id(self,idx):
        # Get time series
        ts_id, lookback_id = self._ids[idx]
        ts = self.items[ts_id]
        if isinstance(ts,tuple):
            ts = ts[0] # no idea why they become tuples
        # Prepare input and target. Zero pad if necessary.
        if ts.shape[-1] < self.lookback + self.horizon:
            # If the time series is too short, we zero pad
            x = ts[:, :-self.horizon]
            x = np.pad(
                x,
                pad_width=((0, 0), (self.lookback - x.shape[-1], 0)),
                mode='constant',
                constant_values=0
            )
            y = ts[:,-self.horizon:]
        else:
            x = ts[:,lookback_id:lookback_id + self.lookback]
            y = ts[:,lookback_id + self.lookback:lookback_id + self.lookback + self.horizon]
        return x, y

    def shuffle_fn(self, idxs):
        self.items.shuffle()
        return idxs

    def create_item(self, idx):
        if idx>=self.n: raise IndexError
        x, y = self.get_id(idx)
        return TSTensorSeq(x),TSTensorSeqy(y, x_len=x.shape[1], m='-*g')


# Cell

from fastai2.vision.data import *

@typedispatch
def show_batch(x: TensorSeq, y, samples, ctxs=None, max_n=10,rows=None, cols=None, figsize=None, **kwargs):
    if ctxs is None: ctxs = get_grid(min(len(samples), max_n), rows=rows, cols=cols, add_vert=1, figsize=figsize)
    ctxs = show_batch[object](x, y, samples=samples, ctxs=ctxs, max_n=max_n, **kwargs)
    return ctxs


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
def concat_ts_list(train, val, lookback = 72):
    items=L()
    assert len(train) == len(val)
    for t, v in zip(train, val):
        items.append(np.concatenate([t[:, -lookback:],v],1))
    return items

# Cell
def sep_last(items, pct = .2):
    train,valid=L(),L()
    for ts in items:
        split_idx = int((1-pct)*ts.shape[1])
        train.append(ts[:,:split_idx])
        valid.append(ts[:,split_idx:])
    return train, valid

# Cell
def IndexsSplitter(train_idx, val_idx=None, test=None):
    """Split `items` from 0 to `train_idx` in the training set, from `train_idx` to `val_idx` (or the end) in the validation set.

    Optionly if `test` will  in test set will also make test from val_idx to end.
    """
    val_idx = ifnone(val_idx,len(items))
    do_test = ifnone(test, False)

    def _inner(items, **kwargs):
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
def TSBlock():
    return TransformBlock(dl_type=TSDataLoader,)

# Cell
class TSDataBunch(DataBunch):
    @classmethod
    @delegates(DataBunch.from_dblock)
    def from_folder(cls, path, valid_pct=.2, seed=None, horizon=None, lookback=None, step=1, nrows=None, skiprows=None, **kwargs):
        "Create from M-compition style in `path` with `train`,`test` csv-files. "
        train, test = get_ts_files(path, nrows=nrows, skiprows=skiprows)
        horizon = ifnone(horizon, len(test[0]))
        lookback = ifnone(lookback, horizon * 3)
        test = concat_ts_list(train, test, lookback)
        train, valid = sep_last(train, valid_pct)
        splits = IndexsSplitter(len(train),len(valid), True)(items)
        dsrc = DataSource(L(*train,*valid,*test), splits=splits, dl_type=TSDataLoader)
        return dsrc.databunch(bs=16, horizon=horizon, lookback=lookback, step=step)

#     @classmethod
#     @delegates(DataBunch.from_dblock)
#     def from_df(cls, df, path='.', valid_pct=0.2, seed=None, text_col=0, label_col=1, label_delim=None, y_block=None,
#                 text_vocab=None, is_lm=False, valid_col=None, **kwargs):
#         if y_block is None and not is_lm: y_block = MultiCategoryBlock if is_listy(label_col) and len(label_col) > 1 else CategoryBlock
#         if is_lm: y_block = []
#         if not isinstance(y_block, list): y_block = [y_block]
#         splitter = RandomSplitter(valid_pct, seed=seed) if valid_col is None else ColSplitter(valid_col)
#         dblock = DataBlock(blocks=(TextBlock(text_vocab, is_lm), *y_block),
#                            get_x=ColReader(text_col),
#                            get_y=None if is_lm else ColReader(label_col, label_delim=label_delim),
#                            splitter=splitter)
#         return cls.from_dblock(dblock, df, path=path, **kwargs)

#     @classmethod
#     def from_csv(cls, path, csv_fname='labels.csv', header='infer', delimiter=None, **kwargs):
#         df = pd.read_csv(Path(path)/csv_fname, header=header, delimiter=delimiter)
#         return cls.from_df(df, path=path, **kwargs)

# TextDataBunch.from_csv = delegates(to=TextDataBunch.from_df)(TextDataBunch.from_csv)