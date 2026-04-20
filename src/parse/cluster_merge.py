"""
레이아웃 클러스터 후처리: 분리된 리스트 마커를 본문과 병합하는 모듈

====================================================================
문제 상황:
====================================================================
    Docling의 레이아웃 분석 AI 모델이 PDF를 분석할 때,
    ⑴, ⑵, ㈎ 같은 작은 리스트 마커(번호 기호)를 본문 텍스트와 분리된
    별도의 클러스터(텍스트 블록)로 인식하는 경우가 있습니다.

    예시 - 원본 PDF에서는 이렇게 보임:
        ⑴ 매출액은 전년 대비 10% 증가하였다.
        ⑵ 영업이익률은 5.3%를 기록하였다.

    Docling이 잘못 분리한 결과:
        클러스터1: "⑴"           (마커만 따로)
        클러스터2: "매출액은 전년 대비 10% 증가하였다."  (본문만 따로)
        클러스터3: "⑵"           (마커만 따로)
        클러스터4: "영업이익률은 5.3%를 기록하였다."     (본문만 따로)

====================================================================
해결 방법:
====================================================================
    이 모듈은 후처리 단계에서 분리된 마커 클러스터를 인접한 본문 클러스터에
    다시 병합합니다. 병합 조건은 다음 3가지를 모두 만족해야 합니다:
        1. 같은 행(가로줄)에 있어야 함 (top 좌표가 비슷)
        2. 마커가 본문 왼쪽에 위치해야 함
        3. 마커 클러스터의 크기가 작아야 함 (가로·세로 30px 이하)
"""


import logging
from src.parse.parser_dtos import _MARKER_RE
from docling.datamodel.base_models import BoundingBox, Cluster

# 로거 설정
_log = logging.getLogger(__name__)


def _is_marker_cluster(cluster: Cluster, max_width: float = 30, max_height: float = 30) -> bool:
    """
    주어진 클러스터가 리스트 마커(번호 기호)인지 판단합니다.

    판단 기준:
        1. 크기가 작아야 함 (가로 30px, 세로 30px 이하)
        2. 텍스트가 비어있지 않아야 함
        3. 다음 중 하나를 만족:
           a) 마커 정규표현식 패턴에 매칭됨 (⑴, ㈎, ①, (1), 1. 등)
           b) 텍스트가 3자 이하이면서 AI 모델의 confidence(확신도)가 낮음 (0.6 미만)
              → AI가 뭔지 잘 모르겠는 작은 텍스트 = 마커일 가능성 높음

    Args:
        cluster: 판단할 클러스터 (Docling의 Cluster 객체)
        max_width: 마커로 인정할 최대 가로 크기 (픽셀 단위)
        max_height: 마커로 인정할 최대 세로 크기 (픽셀 단위)

    Returns:
        True면 마커 클러스터, False면 일반 클러스터

    참고 - Bounding Box 좌표계:
        cluster.bbox는 클러스터를 감싸는 사각형(bounding box)입니다.
        좌표는 다음과 같이 구성됩니다:
            l (left)   : 왼쪽 x 좌표
            r (right)  : 오른쪽 x 좌표
            t (top)    : 위쪽 y 좌표
            b (bottom) : 아래쪽 y 좌표
        따라서 가로 크기 = r - l, 세로 크기 = b - t 입니다.
    """
    # 클러스터의 가로/세로 크기를 계산합니다.
    w = cluster.bbox.r - cluster.bbox.l  # 가로 크기 (width)
    h = cluster.bbox.b - cluster.bbox.t  # 세로 크기 (height)

    # 크기가 너무 크면 마커가 아님 → False 반환
    if w > max_width or h > max_height:
        return False

    # 클러스터 안의 모든 셀(cell)의 텍스트를 합쳐서 하나의 문자열로 만듦
    # strip()은 앞뒤 공백을 제거합니다.
    text = "".join(cell.text for cell in cluster.cells).strip()

    # 텍스트가 비어있으면 마커가 아님
    if not text:
        return False

    # 조건 a: 마커 정규표현식 패턴에 매칭되는지 확인
    # (parser_dtos.py에 정의된 _MARKER_RE 패턴 참고)
    if _MARKER_RE.match(text):
        return True

    # 조건 b: 짧은 텍스트(3자 이하) + 낮은 confidence → 마커 후보로 판단
    # confidence는 0~1 사이의 값으로, AI 모델이 "이 클러스터가 무엇인지"
    # 얼마나 확신하는지를 나타냅니다. 낮을수록 불확실합니다.
    if len(text) <= 3 and cluster.confidence < 0.6:
        return True

    return False


def _is_same_row(a: Cluster, b: Cluster, tolerance: float = 15) -> bool:
    """
    두 클러스터가 같은 행(가로줄)에 있는지 판단합니다.

    PDF에서 같은 줄에 있는 텍스트라도 정확히 같은 y좌표를 갖지는 않습니다.
    (폰트 크기 차이, 정렬 오차 등의 이유로)
    그래서 top(위쪽) 좌표의 차이가 tolerance(허용 오차) 이내이면
    같은 행으로 판단합니다.

    Args:
        a: 첫 번째 클러스터
        b: 두 번째 클러스터
        tolerance: 같은 행으로 인정할 y좌표 차이의 최대값 (픽셀 단위, 기본 15)

    Returns:
        True면 같은 행, False면 다른 행
    """
    return abs(a.bbox.t - b.bbox.t) < tolerance


def _is_left_adjacent(marker: Cluster, body: Cluster, max_gap: float = 30) -> bool:
    """
    마커 클러스터가 본문 클러스터의 왼쪽에 인접해 있는지 판단합니다.

    조건:
        - 마커의 오른쪽 끝(marker.bbox.r)이 본문의 왼쪽 시작(body.bbox.l)보다
          왼쪽에 있어야 함 (gap >= 0, 즉 마커가 본문보다 왼쪽)
        - 그 간격(gap)이 max_gap(기본 30px) 이하여야 함
          (너무 멀리 떨어져 있으면 관련 없는 클러스터)

    시각적 예시:
        [마커]  ← gap →  [본문 클러스터]
              ↑ 이 간격이 0~30px 이내여야 함

    Args:
        marker: 마커 클러스터
        body: 본문 클러스터
        max_gap: 인접으로 인정할 최대 간격 (픽셀 단위, 기본 30)

    Returns:
        True면 왼쪽에 인접, False면 아님
    """
    gap = body.bbox.l - marker.bbox.r  # 본문 왼쪽 - 마커 오른쪽 = 간격
    return 0 <= gap <= max_gap


def merge_marker_clusters(clusters: list[Cluster]) -> list[Cluster]:
    """
    분리된 리스트 마커 클러스터를 인접한 본문 클러스터에 병합합니다.

    전체 처리 흐름:
        1단계: 모든 클러스터를 마커 vs 본문으로 분류
        2단계: 각 마커에 대해 가장 가까운 본문 클러스터를 찾음
               (같은 행 + 왼쪽 인접 + 가장 가까운 것)
        3단계: 찾은 매칭 정보를 바탕으로 실제 병합 수행
               - 마커의 셀(cell)을 본문에 추가
               - bounding box를 마커를 포함하도록 확장
               - 마커 클러스터는 결과에서 제거

    Args:
        clusters: Docling이 분석한 클러스터(텍스트 블록) 리스트

    Returns:
        마커가 병합된 새로운 클러스터 리스트
        (병합할 마커가 없으면 원본 리스트를 그대로 반환)
    """
    # 빈 리스트가 들어오면 바로 반환
    if not clusters:
        return clusters

    # ── 1단계: 클러스터 분류 ──
    # 각 클러스터의 인덱스(위치 번호)를 마커/본문으로 나눕니다.
    markers: list[int] = []   # 마커 클러스터의 인덱스 목록
    bodies: list[int] = []    # 본문 클러스터의 인덱스 목록

    for i, c in enumerate(clusters):
        if _is_marker_cluster(c):
            markers.append(i)
        else:
            bodies.append(i)

    # 마커가 하나도 없으면 병합할 것이 없으므로 원본 반환
    if not markers:
        return clusters

    # ── 2단계: 각 마커에 대해 병합할 본문 찾기 ──
    # merged_to 딕셔너리: {마커 인덱스 → 병합 대상 본문 인덱스}
    merged_to: dict[int, int] = {}

    for m_idx in markers:
        marker = clusters[m_idx]
        best_body: int | None = None   # 가장 적합한 본문의 인덱스
        best_gap = float("inf")        # 가장 가까운 간격 (초기값: 무한대)

        for b_idx in bodies:
            body = clusters[b_idx]

            # 조건 1: 같은 행에 있어야 함
            if not _is_same_row(marker, body):
                continue
            # 조건 2: 마커가 본문 왼쪽에 인접해야 함
            if not _is_left_adjacent(marker, body):
                continue

            # 위 조건을 모두 만족하는 본문 중 가장 가까운 것을 선택
            gap = body.bbox.l - marker.bbox.r
            if gap < best_gap:
                best_gap = gap
                best_body = b_idx

        # 적합한 본문을 찾았으면 매칭 정보를 저장
        if best_body is not None:
            merged_to[m_idx] = best_body

    # 매칭된 마커가 하나도 없으면 원본 반환
    if not merged_to:
        return clusters

    # ── 3단계: 실제 병합 수행 ──
    result_clusters: list[Cluster] = []
    # 병합될 마커들의 인덱스 집합 (이 클러스터들은 결과에서 제외됨)
    skip_indices = set(merged_to.keys())

    for i, cluster in enumerate(clusters):
        # 이미 다른 본문에 병합된 마커는 건너뜀
        if i in skip_indices:
            continue

        # 이 본문 클러스터(i)에 병합되는 마커들을 수집
        # merged_to.items()에서 b(본문 인덱스)가 현재 i인 마커들을 찾음
        merging_markers = [clusters[m] for m, b in merged_to.items() if b == i]

        if merging_markers:
            # ── bounding box 확장 ──
            # 본문과 마커의 bounding box를 모두 포함하는 새로운 bounding box를 계산합니다.
            # 가장 작은 l/t와 가장 큰 r/b를 선택하면 모든 box를 감싸는 큰 box가 됩니다.
            all_bboxes = [cluster.bbox] + [m.bbox for m in merging_markers]
            new_bbox = BoundingBox(
                l=min(b.l for b in all_bboxes),  # 가장 왼쪽
                t=min(b.t for b in all_bboxes),  # 가장 위쪽
                r=max(b.r for b in all_bboxes),  # 가장 오른쪽
                b=max(b.b for b in all_bboxes),  # 가장 아래쪽
            )

            # ── 셀(cell) 병합 ──
            # 마커의 셀을 본문 셀 앞에 추가합니다.
            # (마커가 본문 왼쪽에 있으므로, 읽는 순서상 마커가 먼저 와야 합니다)
            # sorted()로 마커들을 왼쪽→오른쪽 순서로 정렬합니다.
            merged_cells = []
            for m in sorted(merging_markers, key=lambda m: m.bbox.l):
                merged_cells.extend(m.cells)  # 마커의 셀들을 먼저 추가
            merged_cells.extend(cluster.cells)  # 그 뒤에 본문 셀들을 추가

            # 본문 클러스터의 bbox와 cells를 업데이트
            cluster.bbox = new_bbox
            cluster.cells = merged_cells

            # 디버깅용 로그: 어떤 마커가 어디에 병합되었는지 기록
            marker_texts = [
                "".join(c.text for c in m.cells).strip() for m in merging_markers
            ]
            _log.info(
                f"마커 병합: {marker_texts} → "
                f"[{cluster.label.value}] "
                f"{''.join(c.text for c in cluster.cells[:2]).strip()[:30]}..."
            )

        result_clusters.append(cluster)

    # 최종 결과 로그: 몇 건이 병합되었고, 클러스터 수가 어떻게 변했는지 기록
    _log.info(f"마커 병합: {len(merged_to)}건 처리, {len(clusters)}→{len(result_clusters)}개 클러스터")
    return result_clusters


# ======================================================================
# 근접 클러스터링 — 공간적으로 가까운 아이템끼리 묶기
# ======================================================================
# reading order 정렬 전에, 가까이 있는 요소들을 하나의 클러스터로 묶어서
# "한 덩어리"로 읽히도록 합니다.
# 주변에 더 이상 가까운 context가 없을 때까지 계속 묶습니다 (Union-Find).

from src.parse.parser_dtos import _ItemInfo, CLUSTER_DISTANCE_FACTOR


def _bbox_distance(a: _ItemInfo, b: _ItemInfo) -> float:
    """두 아이템 bbox 사이 최단 거리 (겹치면 0)"""
    dx = max(0.0, max(a.left - b.right, b.left - a.right))
    dy = max(0.0, max(a.top - b.bottom, b.top - a.bottom))
    return (dx ** 2 + dy ** 2) ** 0.5


def _avg_item_height(items: list[_ItemInfo]) -> float:
    heights = [i.bottom - i.top for i in items if i.bottom > i.top]
    return sum(heights) / len(heights) if heights else 20.0


def cluster_nearby_items(items: list[_ItemInfo]) -> list[list[_ItemInfo]]:
    """공간적으로 가까운 아이템끼리 클러스터로 묶습니다 (Union-Find).

    거리 임계값 = 평균 아이템 높이 × CLUSTER_DISTANCE_FACTOR
    주변에 더 이상 가까운 아이템이 없을 때까지 반복적으로 묶습니다.

    Args:
        items: 한 페이지 내 아이템 리스트

    Returns:
        클러스터 리스트. 각 클러스터는 _ItemInfo 리스트.
        클러스터 간 순서는 (min_top, min_left) 기준 Top→Down, Left→Right.
    """
    if len(items) <= 1:
        return [items] if items else []

    max_dist = _avg_item_height(items) * CLUSTER_DISTANCE_FACTOR
    n = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if _bbox_distance(items[i], items[j]) <= max_dist:
                union(i, j)

    groups: dict[int, list[_ItemInfo]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(items[i])

    # 클러스터 간 순서: Top→Down, Left→Right
    sorted_clusters = sorted(
        groups.values(),
        key=lambda c: (min(i.top for i in c), min(i.left for i in c)),
    )
    return sorted_clusters
