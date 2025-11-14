/**
 * API 연결 및 관리 파일
 * 모든 API 호출을 중앙에서 관리
 */

// 서버 실행 방법: python -m src.main 또는 uvicorn src.main:app --host 0.0.0.0 --port 8000
const API_BASE_URL = 'http://192.168.14.95:8000'; // 서버 IP 주소

/**
 * API 호출 유틸리티 함수
 * @param {string} endpoint - API 엔드포인트
 * @param {object} options - fetch 옵션
 * @returns {Promise} API 응답
 */
async function apiCall(endpoint, options = {}) {
    try {
        const url = `${API_BASE_URL}${endpoint}`;
        console.log('🔗 API 호출 URL:', url);
        
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        };

        const response = await fetch(url, { ...defaultOptions, ...options });
        console.log('📡 응답 상태:', response.status, response.statusText);
        console.log('📡 응답 URL:', response.url);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ 응답 본문:', errorText);
            throw new Error(`API 호출 실패: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        console.log('✅ 응답 데이터:', data);
        return data;
    } catch (error) {
        console.error('❌ API 호출 오류:', error);
        console.error('❌ 에러 타입:', error.name);
        console.error('❌ 에러 메시지:', error.message);
        if (error.cause) {
            console.error('❌ 에러 원인:', error.cause);
        }
        throw error;
    }
}

/**
 * 서울특별시 자치구별 매장 수 통계 조회
 * @returns {Promise<Array>} 자치구별 매장 수 데이터
 */
async function getDistrictStats() {
    try {
        console.log('API 호출 시작: /admin/district-stats');
        const response = await apiCall('/admin/district-stats');
        console.log('API 응답 받음:', response);
        
        if (response && response.data) {
            console.log('데이터 개수:', response.data.length);
            return response.data;
        } else {
            console.warn('응답에 data 필드가 없습니다:', response);
            return [];
        }
    } catch (error) {
        console.error('자치구별 매장 수 조회 오류:', error);
        console.error('에러 상세:', {
            message: error.message,
            stack: error.stack
        });
        throw error; // 에러를 다시 throw하여 상위에서 처리할 수 있도록
    }
}

// 전역으로 export (필요시)
if (typeof window !== 'undefined') {
    window.api = {
        getDistrictStats,
        apiCall
    };
}

