add_library(example_mod SHARED example_mod.c)
target_include_directories(example_mod PRIVATE "${HORSE_SDK_DIR}/include")
set_target_properties(example_mod PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/mods"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/mods"
    OUTPUT_NAME "example_mod"
)
