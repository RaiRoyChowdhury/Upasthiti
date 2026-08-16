from cv.embedding_manager import best_match, cosine_similarity


def test_identical_vectors_have_similarity_one():
    v = [0.1, 0.2, 0.3, 0.4]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_opposite_vectors_have_similarity_negative_one():
    v = [1.0, 0.0]
    w = [-1.0, 0.0]
    assert abs(cosine_similarity(v, w) - (-1.0)) < 1e-6


def test_orthogonal_vectors_have_similarity_zero():
    v = [1.0, 0.0]
    w = [0.0, 1.0]
    assert abs(cosine_similarity(v, w)) < 1e-6


def test_zero_vector_returns_zero_similarity_without_crashing():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_best_match_picks_the_closest_candidate():
    probe = [1.0, 0.0, 0.0]
    candidates = [
        ("student_far", [0.0, 1.0, 0.0]),
        ("student_close", [0.95, 0.05, 0.0]),
        ("student_medium", [0.5, 0.5, 0.0]),
    ]
    best_id, score = best_match(probe, candidates)
    assert best_id == "student_close"
    assert score > 0.9


def test_best_match_with_no_candidates_returns_none():
    best_id, score = best_match([1.0, 0.0], [])
    assert best_id is None
    assert score == 0.0
