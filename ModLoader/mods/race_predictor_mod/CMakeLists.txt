add_library(race_predictor_mod SHARED
    race_predictor_mod.c
    race_predictor.c
)

target_include_directories(race_predictor_mod PRIVATE
    "${HORSE_SDK_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}"
)

target_link_libraries(race_predictor_mod PRIVATE horse_sdk)

set_target_properties(race_predictor_mod PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/mods"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/mods"
    OUTPUT_NAME "race_predictor_mod"
)
