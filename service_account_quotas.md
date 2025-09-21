## Google Drive Service Account Quota Limits

### API Request Quotas:
1. **Queries per day**: 1,000,000,000 requests/day
2. **Queries per 100 seconds**: 1,000 requests/100s
3. **Queries per 100 seconds per user**: 100 requests/100s per user

### Upload/Download Quotas:
4. **Upload quota**: 750 GB/day per user
5. **Download quota**: 10 TB/day per user

### Storage Quotas:
6. **Storage**: Service Account sử dụng quota của tài khoản owner
7. **Files per folder**: 500,000 files maximum
8. **File size**: 5 TB maximum per file

### Rate Limiting:
9. **Burst requests**: Limited để tránh abuse
10. **Concurrent uploads**: Limited số lượng upload đồng thời

### Possible Error Scenarios:
- storageQuotaExceeded: Owner account hết dung lượng
- dailyLimitExceeded: Vượt quá giới hạn API requests/day
- userRateLimitExceeded: Vượt quá rate limit per user
- rateLimitExceeded: Vượt quá rate limit chung
- quotaExceeded: Vượt quá các quota khác