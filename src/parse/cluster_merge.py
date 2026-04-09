"""레이아웃 클러스터 후처리: 분리된 리스트 마커를 본문과 병합합니다.

문제:
Docling 레이아웃 모델이 ⑴, ⑵, ㈎ 같은 작은 리스트 마커를 본문과 분리된 별도 클러스터로 감지함.

해결:
작은 마커 클러스터를 인접한 본문 클러스터에 병합하는 후처리 단계 추가
조건: 같은 행(top 좌표 유사) + 마커가 본문 왼쪽에 위치 + 작은 크기
"""


import logging
from src.parse.parser_dtos import _MARKER_RE
from docling.datamodel.base_models import BoundingBox, Cluster

_log = logging.getLogger(__name__)


def _is_marker_cluster(cluster: Cluster, max_width: float = 30, max_height: float = 30) -> bool:
    """작은 클러스터인지 판단 단계"""
    w = cluster.bbox.r - cluster.bbox.l
    h = cluster.bbox.b - cluster.bbox.t

    if w > max_width or h > max_height:
        return False

    text = "".join(cell.text for cell in cluster.cells).strip()
    if not text:
        return False

    # 마커 패턴 매칭
    if _MARKER_RE.match(text):
        return True

    # 짧은 텍스트(3자 이하) + 낮은 confidence도 마커 후보
    if len(text) <= 3 and cluster.confidence < 0.6:
        return True

    return False


def _is_same_row(a: Cluster, b: Cluster, tolerance: float = 15) -> bool:
    """두 클러스터가 같은 행에 있는지 판단합니다 (top 좌표 기준)."""
    return abs(a.bbox.t - b.bbox.t) < tolerance


def _is_left_adjacent(marker: Cluster, body: Cluster, max_gap: float = 30) -> bool:
    """마커가 본문 왼쪽에 인접해 있는지 판단합니다."""
    gap = body.bbox.l - marker.bbox.r
    return 0 <= gap <= max_gap


def merge_marker_clusters(clusters: list[Cluster]) -> list[Cluster]:
    """분리된 리스트 마커를 인접 본문 클러스터에 병합.

    Returns:
        병합된 클러스터 리스트
    """
    if not clusters:
        return clusters

    markers: list[int] = []
    bodies: list[int] = []

    for i, c in enumerate(clusters):
        if _is_marker_cluster(c):
            markers.append(i)
        else:
            bodies.append(i)

    if not markers:
        return clusters

    merged_to: dict[int, int] = {}  # marker_idx → body_idx

    for m_idx in markers:
        marker = clusters[m_idx]
        best_body: int | None = None
        best_gap = float("inf")

        for b_idx in bodies:
            body = clusters[b_idx]

            if not _is_same_row(marker, body):
                continue
            if not _is_left_adjacent(marker, body):
                continue

            gap = body.bbox.l - marker.bbox.r
            if gap < best_gap:
                best_gap = gap
                best_body = b_idx

        if best_body is not None:
            merged_to[m_idx] = best_body

    if not merged_to:
        return clusters

    # 병합 실행
    result_clusters: list[Cluster] = []
    skip_indices = set(merged_to.keys())

    for i, cluster in enumerate(clusters):
        if i in skip_indices:
            continue

        # 이 클러스터에 병합되는 마커들 수집
        merging_markers = [clusters[m] for m, b in merged_to.items() if b == i]

        if merging_markers:
            # bbox 확장
            all_bboxes = [cluster.bbox] + [m.bbox for m in merging_markers]
            new_bbox = BoundingBox(
                l=min(b.l for b in all_bboxes),
                t=min(b.t for b in all_bboxes),
                r=max(b.r for b in all_bboxes),
                b=max(b.b for b in all_bboxes),
            )

            # cells 병합 
            merged_cells = []
            for m in sorted(merging_markers, key=lambda m: m.bbox.l):
                merged_cells.extend(m.cells)
            merged_cells.extend(cluster.cells)

            cluster.bbox = new_bbox
            cluster.cells = merged_cells

            marker_texts = [
                "".join(c.text for c in m.cells).strip() for m in merging_markers
            ]
            _log.info(
                f"마커 병합: {marker_texts} → "
                f"[{cluster.label.value}] "
                f"{''.join(c.text for c in cluster.cells[:2]).strip()[:30]}..."
            )

        result_clusters.append(cluster)

    _log.info(f"마커 병합: {len(merged_to)}건 처리, {len(clusters)}→{len(result_clusters)}개 클러스터")
    return result_clusters
