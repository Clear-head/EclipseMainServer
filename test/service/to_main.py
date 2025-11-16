import asyncio
import time

from src.service.category.category_service import MainScreenService



start_time = time.time()
asyncio.run(MainScreenService().to_main())
end_time = time.time() - start_time

print(end_time)