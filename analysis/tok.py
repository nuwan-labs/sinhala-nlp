"""
Subword tokeniser training (BPE / Unigram / WordPiece) and a grapheme-pair
encoder, for RQ1 (one BPE unit level) and RQ2 (vocab sweep, algorithm sweep).
Trained on the register text only.  Deterministic given SEED.
"""
from __future__ import annotations
import tempfile
from functools import lru_cache

from tokenizers import Tokenizer, models, trainers, pre_tokenizers

from .common import SEED, corpus_text, seg_graphemes


def _train(model_cls, trainer_cls, vocab_size, text, **kw):
    tok = Tokenizer(model_cls())
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    trainer = trainer_cls(vocab_size=vocab_size, special_tokens=["<unk>"], **kw)
    tok.train_from_iterator([text], trainer)
    return tok


@lru_cache(maxsize=None)
def bpe_tokenizer(vocab_size=4000):
    return _train(lambda: models.BPE(unk_token="<unk>"), trainers.BpeTrainer,
                  vocab_size, corpus_text())


@lru_cache(maxsize=None)
def unigram_tokenizer(vocab_size=4000):
    tok = Tokenizer(models.Unigram())
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    trainer = trainers.UnigramTrainer(vocab_size=vocab_size, unk_token="<unk>",
                                      special_tokens=["<unk>"])
    tok.train_from_iterator([corpus_text()], trainer)
    return tok


@lru_cache(maxsize=None)
def wordpiece_tokenizer(vocab_size=4000):
    tok = Tokenizer(models.WordPiece(unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    trainer = trainers.WordPieceTrainer(vocab_size=vocab_size,
                                        special_tokens=["[UNK]"])
    tok.train_from_iterator([corpus_text()], trainer)
    return tok


def encode_units(tok, text):
    """Return the list of subword pieces for `text`."""
    return tok.encode(text).tokens


@lru_cache(maxsize=4)
def _gpe_merges(n_merges=2000):
    """Learn grapheme-pair merges on the corpus once (cached)."""
    from collections import Counter
    corpus = corpus_text()
    words = [seg_graphemes(w) for w in corpus.split()]
    merges = []
    for _ in range(n_merges):
        pairs = Counter()
        for w in words:
            for a, b in zip(w, w[1:]):
                pairs[(a, b)] += 1
        if not pairs:
            break
        (a, b), cnt = pairs.most_common(1)[0]
        if cnt < 3:
            break
        merges.append((a, b))
        new_words = []
        for w in words:
            nw = []
            i = 0
            while i < len(w):
                if i < len(w) - 1 and w[i] == a and w[i + 1] == b:
                    nw.append(a + b)
                    i += 2
                else:
                    nw.append(w[i])
                    i += 1
            new_words.append(nw)
        words = new_words
    return {pair: i for i, pair in enumerate(merges)}


def grapheme_pair_units(text, n_merges=2000):
    """A grapheme-pair encoder: BPE-style merges over grapheme clusters rather
    than bytes (the GPE idea, Velayuthan & Sarveswaran 2025).  Deterministic.
    Returns the encoded unit list for `text`."""
    merge_rank = _gpe_merges(n_merges)

    def apply(word_graphemes):
        w = list(word_graphemes)
        while True:
            best = None
            best_rank = None
            for i, (x, y) in enumerate(zip(w, w[1:])):
                r = merge_rank.get((x, y))
                if r is not None and (best_rank is None or r < best_rank):
                    best_rank = r
                    best = i
            if best is None:
                break
            w[best:best + 2] = [w[best] + w[best + 1]]
        return w

    out = []
    for token in text.split():
        out.extend(apply(seg_graphemes(token)))
    return out
