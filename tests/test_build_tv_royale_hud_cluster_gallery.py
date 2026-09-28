from __future__ import annotations

import numpy as np

from scripts.build_tv_royale_hud_cluster_gallery import cosine_kmeans


def test_cosine_kmeans_is_deterministic_and_separates_directions() -> None:
    vectors = np.asarray(
        [
            [1.0, 0.01, 0.0],
            [0.99, -0.01, 0.0],
            [0.0, 1.0, 0.01],
            [0.01, 0.99, -0.01],
            [0.0, 0.01, 1.0],
            [-0.01, 0.0, 0.99],
        ],
        dtype=np.float32,
    )

    assignments_a, centroids_a = cosine_kmeans(vectors, clusters=3)
    assignments_b, centroids_b = cosine_kmeans(vectors, clusters=3)

    assert np.array_equal(assignments_a, assignments_b)
    assert np.array_equal(centroids_a, centroids_b)
    assert assignments_a[0] == assignments_a[1]
    assert assignments_a[2] == assignments_a[3]
    assert assignments_a[4] == assignments_a[5]
    assert len(set(assignments_a.tolist())) == 3
