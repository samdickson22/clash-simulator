This replay tests one execution change: fit the completed seed1279501/fold0 tree pair with eight OpenMP threads instead of one. It preserves the complete training rows, public features, seeds, loss functions, weights and 100 boosting iterations.

Publish the replay plan only after the guarded serial reference finishes and its original launcher is retired. `supervise.py --mode pin` freezes these sources and all reference resources. `supervise.py --mode run` executes under the shared lease and 18 GiB guard.

Both estimators must match the serial checkpoint exactly after normalizing only the copied bin mapper's thread-count field. Prediction shapes, dtypes and bytes must match on all 2,465,152 rows. Signed zero remains part of the byte comparison. The actual eight-thread checkpoint is retained with its original thread metadata.

The two synthetic tests verify the exactness checks themselves. The earlier synthetic thread proof does not establish full-corpus equality. This replay permits no remaining production fits; a continuation authority is required after its state, prediction and memory checks pass. No model-quality criterion selects the thread count.
