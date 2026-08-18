# @api_view(['GET'])
# def CategoryViewApi(request):
#     slug = request.GET.get('slug')

#     if slug:
#         category = Category.objects.select_related('parent').filter(
#             slug=slug.lower()
#         ).first()

#         # Prevent NoneType crash
#         if not category:
#             return Response(
#                 {"error": "Category not found"},
#                 status=404
#             )

#         subcategories = Category.objects.select_related('parent').filter(
#             parent__slug=slug.lower()
#         ).order_by('created_at')

#         # MPTT
#         all_sub = category.get_descendants(include_self=True)

#         brand = Brand.objects.prefetch_related(
#             'productbrands'
#         ).filter(
#             productbrands__category__in=all_sub
#         ).distinct()

#         serializer = CategorySerializer(category)

#         subcategories_serializer = CategorySerializer(
#             subcategories,
#             many=True
#         )

#         brandserializer = BrandSerializer(
#             brand,
#             many=True
#         )

#         return Response({
#             "category": serializer.data,
#             "subcategories": subcategories_serializer.data,
#             "brand": brandserializer.data,
#         })

#     else:
#         categories = Category.objects.select_related('parent').filter(
#             parent__isnull=True
#         ).order_by('created_at')

#         serializer = CategorySerializer(categories, many=True)

#         return Response(serializer.data)