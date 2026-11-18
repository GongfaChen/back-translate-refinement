This chapter discusses the role of the attention mechanism in large-scale language models. Compared with recurrent networks, self-attention can model dependencies over arbitrary distances within a constant path length, and its time complexity is $O(n^2)$[1].

如图 <KEEP:figure:1> shows, the encoder is composed of 6 identical stacked layers, each of which contains two sublayers: self-attention and a <KEEP:math:1> feed-forward network.

The experiments were conducted on 8 GPUs with a batch size of 4096 and a learning rate of 0.0001, training 12M parameters.

The training objective is to minimize the cross-entropy loss, which is denoted as follows, where N is the number of samples.

The focus mechanism can be written as <KEEP:math:2>, where Q, K, and V are the query, key, and value matrices[2,3].

The comparison results of the models are given in the following table, with the parameter count increasing from 21M to 340M.
