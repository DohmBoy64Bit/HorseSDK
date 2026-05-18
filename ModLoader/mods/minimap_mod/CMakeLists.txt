add_library(minimap_mod SHARED
    minimap_mod.c
    map_atlas.c
    map_raster.c
    map_window.c
)

target_include_directories(minimap_mod PRIVATE
    "${HORSE_SDK_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}"
)

target_link_libraries(minimap_mod PRIVATE horse_sdk horse_data)

set_target_properties(minimap_mod PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/mods"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/mods"
    OUTPUT_NAME "minimap_mod"
)
