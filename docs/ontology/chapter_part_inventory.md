# 1~15장 원문 파트 인벤토리

기준 원천: `data/llm_parsed/제1장~제15장*.md`

이 문서는 장별 설계 문서가 원문에 없는 part를 있는 것처럼 가정하지 않도록 만든 검증 표이다. 장별 설계 문서의 `문서 파트 분리` 섹션은 이 표를 기준으로 보정한다.

| 장 | 본문 범위 | terms | application_guidance | basis_for_conclusions | practical_guidance | example | 비고 |
|---:|---|---|---|---|---|---|---|
| 1 | 1.1~1.4 | absent | mentioned in 1.2 only | mentioned in 1.2/1.4 only | mentioned in 1.2/1.4 only | mentioned in 1.2/1.4 only | 제1장은 기준 구성/해석 원칙을 설명하며 별도 부록 파트 없음 |
| 2 | 2.1~2.90 | absent | absent | present | present | present | 부록에 결론도출근거, 실무지침, 적용사례 존재 |
| 3 | 3.1~3.21 | absent | absent | present | present | present | 결론도출근거가 두 구간으로 파싱됨 |
| 4 | 4.1~4.22 | present | absent | present | present | present | 4.4에 용어의 정의 존재. 본문 번호 중 결번/삭제 조항 가능성 별도 확인 필요 |
| 5 | 5.1~5.24 | absent | absent | present | present | absent | 독립 적용사례 파트 없음 |
| 6 | 6.1~6.102 | present | present, 6.A1~6.A26 | present | present | present | 절별 부록이 여러 번 등장 |
| 7 | 7.1~7.24 | present in main | absent | absent | present | absent | 7.3 재고자산의 정의는 본문 정의 조항이며 별도 terms part는 없음 |
| 8 | 8.1~8.37 | present in main | absent | present | present | present | 8.3~8.4 등 본문 정의 조항 존재. 적용사례 존재 |
| 9 | 9.1~9.19 | present in main | absent | absent | present | absent | 9.2~9.4 본문 정의 조항 존재. 독립 결론도출근거/적용사례 없음 |
| 10 | 10.1~10.50 | present in main | absent | present | present | present | 10.4 유형자산의 정의는 본문 정의 조항이며 별도 terms part는 없음 |
| 11 | 11.1~11.41 | present in main | absent | absent | present | absent | 11.2~11.4 식별가능성 정의는 본문 정의 조항이며 별도 terms part는 없음 |
| 12 | 12.1~12.40 | present | absent | absent | present, 실12.1~실12.45 | present in guidance | 결12.* 없음 |
| 13 | 13.1~13.38 | present | absent | present | present | present | 본문 중 용어의 정의가 별도 섹션으로 존재 |
| 14 | 14.1~14.24 | present | absent | present, 결14.1 | present, 실14.1~실14.13 | present | 인식 의사결정 도식 포함 |
| 15 | 15.1~15.25 | absent | absent | absent | present, 실15.1~실15.6 | present | 복합금융상품 사례 다수 |

## 적용 원칙

- `present`인 part만 장별 `document_parts`와 설계 문서의 part 표에 넣는다.
- `absent`인 part는 “있는 경우”라고 쓰지 않고 명시적으로 `absent`로 표시한다.
- 제1장처럼 본문에서 부록 구성을 설명만 하는 경우 실제 part로 보지 않는다.
- 사례가 실무지침 안에 포함되어 있으면 `example`은 존재하지만 권위 수준은 사례로 둔다.
- 결론도출근거는 항상 `BASIS_FOR`로 연결하고 `SUPPLEMENTS`로 연결하지 않는다.
