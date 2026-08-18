from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class ProductPagination(PageNumberPagination):
    page_size = 10

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["current_page"] = self.page.number
        response.data["total_pages"] = self.page.paginator.num_pages
        return response
    

    