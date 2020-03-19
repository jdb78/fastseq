# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_data.core.ipynb (unless otherwise specified).

__all__ = ['NormalizeSeq', 'NormalizeSeqMulti', 'make_test', 'split_file', 'TSSplitter', 'get_train_valid_ts',
           'split_for_m5', 'MTSDataLoaders', 'from_m5_path', 'from_path', 'from_folders']

# Cell
from ..core import *
from .external import *
from .load import *
from .procs import *
from fastcore.all import *
from fastcore.imports import *
from fastai2.basics import *
from fastai2.data.transforms import *
from fastai2.tabular.core import *
import orjson

# Cell
def _zeros_2_ones(o, eps=1e-8):
    nan_mask = o!=o
    o[o < eps ] = 1
    o[nan_mask ] = 1
    return o


# Cell
class NormalizeSeq(Transform):
    def __init__(self, verbose=False, make_ones=True, eps=1e-7, mean = None):
        store_attr(self,'verbose, make_ones, eps, mean')
        self.m, self.s = 0, 1

    def to_same_device(self, o):
        if o.is_cuda:
            self.m, self.s = to_device(self.m,'cuda'), to_device(self.s,'cuda')
        else:
            self.m, self.s = to_cpu(self.m), to_cpu(self.s)

    def encodes(self, o: TensorSeq):
        self.m = torch.mean(o, -1, keepdim=True)
        self.s = torch.std(o,  -1, keepdim=True) +self.eps
        if (self.s < self.eps*10).sum():
            self.s = _zeros_2_ones(self.s, self.eps*10)
        if self.verbose:
            print('encodes',[a.shape for a in o],
                  'm shape', {k:o.shape for k,o in self.m.items()},
                  's shape',{k:o.shape for k,o in self.s.items()})

        return self.norm(o)

    def norm(self, o):
        return (o - self.m)/self.s

    def decodes(self, o: TensorSeq):
        if self.verbose:
            print('decodes',o.shape,
                  'm shape',self.m.shape,
                  's shape',self.s.shape)
        return self.denorm(o)

    def denorm(self, o):
        self.to_same_device(o)
        return (o*self.s)+self.m

# Cell
class NormalizeSeqMulti(ItemTransform):
    """A shell Transformer to normalize `TensorSeqs` inside `TSMulti_` with `NormalizeSeqs`. """
    @delegates(NormalizeSeq.__init__)
    def __init__(self, n_its=5, **kwargs):
        """`n_its` does not include the ts to predict."""
        self.f = {i:NormalizeSeq(**kwargs) for i in range(n_its)}
        self.n = n_its

    def encodes(self, o):
        r = L()
        for i,a in enumerate(o):
            if type(a) is not TensorSeq:
                r.append(a)
            elif i < (self.n-1):
                r.append(self.f[i](a))
            else:
                r.append(self.f[0].norm(o[i]))
        return TSMulti_(r)

    def decodes(self, o):
        r = L(self.f[i].decode(a) for i,a in enumerate(o[:-1]))
        r.append(self.f[0].denorm(o[-1]))
        return TSMulti_(r)


# Cell
def make_test(ts:dict, horizon:int, lookback:int, keep_lookback:bool = False):
    """Splits the every ts in `items` based on `horizon + lookback`*,
    where the last part will go into `val` and the first in `train`.
    *if `keep_lookback`:
        it will only remove `horizon` from `train` otherwise will also remove lookback from `train`.
    """
    train, val = {}, {}
    for k,v in ts.items():
        if k in ['ts_con','ts_cat']:
            if keep_lookback:
                train[k] = {col:o[:-(horizon)] for col, o in v.items()}
            else:
                train[k] = {col:o[:-(horizon+lookback)] for col, o in v.items()}
            val[k] = {col: o[-(horizon+lookback):] for col, o in v.items()}

        elif k == '_length':
            train[k] = v - (horizon if keep_lookback else horizon+lookback)
            val[k] = horizon+lookback
        else:
            train[k] = v
            val[k] = v
    return train, val

# Cell
def _ts_file_names(file, valid_folder='valid', train_folder = 'train',
               post_fix = True, path = None, **kwargs):
    path = ifnone(path, Path(*str(file).split(os.sep)[:-1]))
    for folder, name in zip([train_folder, valid_folder], ['train','val']):
        p = path if folder is None else path / folder
        new_f =  p / file.name
        if new_f.exists() and post_fix:
            new_f = Path(str(new_f).replace('.json', '_' + name + '.json'))
        if not new_f.parent.exists(): new_f.parent.mkdir()
        yield new_f

@delegates(make_test)
def split_file(file, valid_folder='valid', train_folder = 'train',
               post_fix = True, path = None, **kwargs):
    ts = get_ts_datapoint(file)
    t, v = make_test(ts, **kwargs)
    # in the new folder
    r = []
    for part, new_f  in zip([t,v], _ts_file_names(file, valid_folder, train_folder,
                                              post_fix, path = path)):
        open(new_f,'wb').write(orjson.dumps(part))
        r.append(new_f)
    return r

# Cell
@delegates(split_file)
def TSSplitter(**kwargs):
    "Create function that splits `items` between train/val."
    def _inner(o):
        return split_file(o, **kwargs)
    return _inner

# Cell
from typing import List
@delegates(TSSplitter)
def _exe_splitter(files:List[Path], horizon, lookback, valid_pct, splitter=None, num_workers = None,
                 **kwargs):
    splitter = ifnone(splitter, TSSplitter(horizon= horizon + int(valid_pct*horizon),lookback=lookback,
                                **kwargs))
#     print('Excecuting splitter; estimated time:', _time_it(splitter, files[0])*len(files))

    list(_ts_file_names(files[0], **kwargs))
    r = multithread_f(splitter, files, num_workers = num_workers)
    return [o[0] for o in r], [o[1] for o in r]

def _get_train_valid_files(path):
    if (path / 'train').exists():
        train = get_files(path / 'train', extensions='.json', folders = False)
    else:
        train = get_files(path, extensions='.json', folders = False)
    valid = get_files(path / 'valid', extensions='.json', folders = False)
    return train, valid

@delegates(_exe_splitter)
def get_train_valid_ts(path, **kwargs):
    if (path / 'valid').exists():
        train, valid = _get_train_valid_files(path)
    else:
        files = get_files(path, extensions='.json', folders = False)
        train, valid = _exe_splitter(files, **kwargs)
    return train, valid



# Cell
def split_for_m5(path, lookback, horizon = 28, verbose = False):
    """Splits al the files in:
        - Evaluation (`horizon` + `lookback`),
        - Validation (`horizon` + `lookback`),
        - val (`horizon` + `lookback` + 'val_pct' * `horizon`),
        - train (the rest)
        """

    if ((path / 'evaluation').exists() and (path / 'validation').exists() and
        (path / 'val').exists() and (path / 'train').exists()):
        evalu = get_files(path / 'evaluation', extensions='.json', folders = False)
        validation = get_files(path / 'validation', extensions='.json', folders = False)
        val = get_files(path / 'val', extensions='.json', folders = False)
        train = get_files(path / 'train', extensions='.json', folders = False)

    else:
        files = get_files(path, extensions='.json', folders = False)
        (files[0].parent / 'all').mkdir()
        for f in files:
            f.copy(f.parent / 'all' / f.name)
        if verbose: print('moved to all')
        train, evalu = _exe_splitter(files, horizon = horizon, lookback= lookback, valid_pct=0,
                                     splitter = None, keep_lookback=True,
                                     valid_folder='evaluation', train_folder = None,
                                     post_fix = False, path = path)
        if verbose: print('made evalutation')
        train, validation = _exe_splitter(train, horizon = horizon, lookback= lookback,valid_pct=0,
                                          splitter = None, keep_lookback=True,
                                          valid_folder='validation', train_folder = None,
                                          post_fix = False, path = path)
        if verbose: print('made validation')

        train, val = _exe_splitter(train, horizon = horizon, lookback= lookback,valid_pct=2,
                                   splitter = None, keep_lookback=True,
                                   valid_folder='val', train_folder = 'train',
                                   post_fix = False, path = path)
        if verbose: print('made val')

        for f in Path(files[0].parent / 'all').glob('*.json'):
            f.rename(files[0].parent / f.name)
        shutil.rmtree(Path(files[0].parent / 'all'))

    return train, val, validation, evalu


# Cell
class MTSDataLoaders(DataLoaders):
    @classmethod
    @delegates(MTSDataLoader.__init__)
    def _from_folders_list(cls, folders:List[List[Path]], y_name:str, horizon:int, lookback=None, step=1,
                           device=None, norm=True, valid_pct=1.5, splitter = None,
                           procs = None, vocab=None, o2i=None, path = None, **kwargs):
        lookback = ifnone(lookback, horizon * 3)
        device = ifnone(device, default_device())
        path = ifnone(path, folders[0][0].parent.parent)
        if procs:
            p = Pipeline(*procs)
            for files in folders:
                p(files)
        if norm and 'after_batch' not in kwargs:
            kwargs.update({'after_batch':L(NormalizeSeqMulti(n_its=5))})

        db = DataLoaders(*[MTSDataLoader(ds, get_meta(path), y_name, horizon=horizon, lookback=lookback, step=step,
                                        device=device, vocab=vocab, o2i=o2i, **kwargs)
                           for ds in folders], path=path, device=device)

        print({k:db[i].n for i,k in zip(range(len(folders)),
                                        ['Train','Val','Validation','Evaluation',*['ds_'+str(j) for j in range(4,100)]])})
        return db

@delegates(MTSDataLoaders._from_folders_list)
def from_m5_path(cls, path:Path, y_name:str, horizon:int, lookback = None, verbose = False, procs = [], **kwargs):
    """Create `MTSDataLoaders` from a path.
    Defaults to splitting the data according to the M5 compitetion.
    """
    lookback = ifnone(lookback, horizon * 3)
    vocab, o2i = make_vocab(path)
    train, val, validation, evalu = split_for_m5(path, lookback, horizon, verbose = verbose)
    procs = L(procs) + CatProc(path, vocab = vocab, o2i = o2i)
    return cls._from_folders_list(folders = [train, val, validation, evalu],
                                  y_name= y_name, horizon= horizon, lookback = lookback,
                                  vocab=vocab, o2i=o2i, path = path,
                                  procs = procs,**kwargs)
MTSDataLoaders.from_m5_path = classmethod(from_m5_path)


# Cell
@delegates(MTSDataLoaders._from_folders_list)
def from_path(cls, path:Path, y_name:str, horizon:int, lookback = None, valid_pct = 1.5, **kwargs):
    """Create `MTSDataLoaders` from a path.
    Defaults to splitting in train and validation set.
    """
    lookback = ifnone(lookback, horizon * 3)
    vocab, o2i = make_vocab(path)
    train, valid = get_train_valid_ts(path, horizon = horizon, lookback = lookback, valid_pct= valid_pct)
    return cls._from_folders_list(folders = [train, valid], y_name= y_name, horizon= horizon, lookback = lookback,
                                  vocab=vocab, o2i=o2i, path = path, **kwargs)

MTSDataLoaders.from_path = classmethod(from_path)

# Cell
@delegates(MTSDataLoaders._from_folders_list)
def from_folders(cls, folders:List[Path], y_name:str, horizon:int, **kwargs):
    """Create `MTSDataLoaders` from the folders."""
    folders = [get_files(path, extensions='.json', folders = False) for path in folders]
    vocab, o2i = make_vocab(folders[0][0].parent.parent)
    return cls._from_folders_list(folders, y_name, horizon,vocab=vocab, o2i=o2i, **kwargs)

MTSDataLoaders.from_folders = classmethod(from_folders)
