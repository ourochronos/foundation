# Snapshot: the 10,479-proposition / 36-domain space

Frozen 2026-07-22 before the gen4 corpus merge rebuilt the whitener. Every
number in decisions.md D10, D16, D17, D18, D19 and D20 was measured against
these artifacts, and reproducing them requires this whitened space — the amp
subspace and the pair-embedding cache are only valid in the space they were
fit in.

Contents: clean_v0.jsonl (corpus), dense_v0.npy (BGE-M3 dense, row-aligned),
whiten_v0.npz (ZCA), sparse_v0.json (lexical identity channel),
prop_relation_emb.npz (whitened pair cache, 23 types),
amp_subspace_v0/_v1.npz (D16 g=2.0 / D20 g=8.0), struct_pooler_v2.pt,
decoder_v0/ (the 10.5k/12-epoch decoder behind D10's 0.178/0.278 point and
the D19 interpolation curve — the live checkpoint dir is overwritten in place
by every retrain).

To reproduce: point the scripts' ROOT-relative paths here, or copy back over
results/ and data/clean_v0.jsonl.
