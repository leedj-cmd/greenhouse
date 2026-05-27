-- ============================================================
-- Greenhouse Farm Disease Detection App
-- PostgreSQL Database Schema
-- Version: 1.0
-- Date: 2026-05-27
-- ============================================================

-- 확장 모듈 활성화
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. fields (밭 정보)
-- ============================================================
CREATE TABLE IF NOT EXISTS fields (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    location    VARCHAR(255),
    status      VARCHAR(50)  NOT NULL DEFAULT 'healthy'
                    CHECK (status IN ('healthy', 'warning', 'critical')),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  fields            IS '비닐하우스 밭(구역) 정보';
COMMENT ON COLUMN fields.status     IS '구역 상태: healthy(정상) | warning(주의) | critical(위험)';

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_fields_updated_at
    BEFORE UPDATE ON fields
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 기본 5개 밭 데이터 삽입
INSERT INTO fields (name, location, status) VALUES
    ('1번 밭', '구역 A - 북쪽',  'healthy'),
    ('2번 밭', '구역 B - 북동쪽', 'healthy'),
    ('3번 밭', '구역 C - 동쪽',  'healthy'),
    ('4번 밭', '구역 D - 남동쪽', 'healthy'),
    ('5번 밭', '구역 E - 남쪽',  'healthy')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 2. analysis_results (AI 분석 결과)
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_results (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id         INTEGER     NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    image_path       VARCHAR(500),
    disease_detected BOOLEAN     NOT NULL DEFAULT FALSE,
    disease_type     VARCHAR(100),           -- 'powdery_mildew', 'leaf_spot', 'blight' 등 / 정상이면 NULL
    confidence       FLOAT       CHECK (confidence >= 0.0 AND confidence <= 1.0),
    raw_output       TEXT,                   -- 모델 원본 출력 (JSON 문자열 권장)
    timestamp        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  analysis_results                  IS 'AI 질병 분석 결과';
COMMENT ON COLUMN analysis_results.disease_type     IS '감지된 질병 유형. 정상일 경우 NULL';
COMMENT ON COLUMN analysis_results.confidence       IS '모델 신뢰도 (0.0 ~ 1.0)';
COMMENT ON COLUMN analysis_results.raw_output       IS '모델 원본 출력값 (JSON 형식 권장)';

-- 조회 성능을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_analysis_field_id  ON analysis_results(field_id);
CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON analysis_results(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_disease   ON analysis_results(disease_detected);


-- ============================================================
-- 3. notifications (알림 기록)
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id    INTEGER     NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    analysis_id UUID        REFERENCES analysis_results(id) ON DELETE SET NULL,
    message     TEXT        NOT NULL,
    sent_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at     TIMESTAMP                                       -- NULL = 미확인
);

COMMENT ON TABLE  notifications          IS '앱 알림 발송 기록';
COMMENT ON COLUMN notifications.read_at  IS '사용자가 알림을 확인한 시각. NULL이면 미확인 상태';

-- 미확인 알림 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_notifications_field_id ON notifications(field_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read_at  ON notifications(read_at) WHERE read_at IS NULL;


-- ============================================================
-- 편의 뷰: 각 밭의 최신 분석 결과 + 현재 상태
-- ============================================================
CREATE OR REPLACE VIEW v_field_latest_status AS
SELECT
    f.id                        AS field_id,
    f.name                      AS field_name,
    f.location,
    f.status                    AS field_status,
    ar.id                       AS latest_analysis_id,
    ar.disease_detected,
    ar.disease_type,
    ar.confidence,
    ar.timestamp                AS last_analyzed_at
FROM fields f
LEFT JOIN LATERAL (
    SELECT *
    FROM   analysis_results
    WHERE  field_id = f.id
    ORDER  BY timestamp DESC
    LIMIT  1
) ar ON TRUE;

COMMENT ON VIEW v_field_latest_status IS '각 밭의 최신 분석 결과를 포함한 현황 뷰';
