// API 호출 함수들
const api = {
    // 구별 통계 조회
    async getDistrictStats() {
        try {
            const response = await fetch('/api/dashboard/district-stats');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('구별 통계 조회 오류:', error);
            throw error;
        }
    },

    // 태그 통계 조회
    async getTagStatistics(categoryType) {
        try {
            const response = await fetch(`/api/dashboard/tag-statistics/${categoryType}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('태그 통계 조회 오류:', error);
            throw error;
        }
    },

    // 인기 장소 조회
    async getPopularPlaces() {
        try {
            const response = await fetch('/api/dashboard/popular-places');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('인기 장소 조회 오류:', error);
            throw error;
        }
    }
};

