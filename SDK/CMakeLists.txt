cmake_minimum_required(VERSION 3.16)
project(HorseSDK VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

option(HORSE_SDK_BUILD_EXAMPLES "Build SDK examples" ON)
option(HORSE_SDK_BUILD_DATA "Build horse_data parsers" ON)
option(HORSE_SDK_BUILD_SAVE_CLI "Build horse_save_cli tool" ON)

# Phase 2 catalog header (generated into include/horse/game_functions.h)
set(HORSE_GAME_FUNCTIONS_H "${CMAKE_CURRENT_SOURCE_DIR}/include/horse/game_functions.h")
if(NOT EXISTS "${HORSE_GAME_FUNCTIONS_H}")
    message(WARNING
        "Missing ${HORSE_GAME_FUNCTIONS_H} — run:\n"
        "  python RE_Tools/tools/scripts/build_game_function_catalog.py")
endif()

add_library(horse_sdk STATIC
    src/module.c
    src/hook.c
)

target_include_directories(horse_sdk
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

if(MSVC)
    target_compile_options(horse_sdk PRIVATE /W4)
else()
    target_compile_options(horse_sdk PRIVATE -Wall -Wextra)
endif()

# Save-file library (Phase 1); lives under RE_Tools until fully merged.
add_subdirectory(
    "${CMAKE_CURRENT_SOURCE_DIR}/../RE_Tools/src/horse_save"
    "${CMAKE_BINARY_DIR}/horse_save"
)

if(HORSE_SDK_BUILD_DATA)
    add_subdirectory(
        "${CMAKE_CURRENT_SOURCE_DIR}/../RE_Tools/src/horse_data"
        "${CMAKE_BINARY_DIR}/horse_data"
    )
endif()

target_link_libraries(horse_sdk PUBLIC horse_save)
if(HORSE_SDK_BUILD_DATA)
    target_link_libraries(horse_sdk PUBLIC horse_data)
endif()

add_library(horse::sdk ALIAS horse_sdk)
add_library(horse::save ALIAS horse_save)

if(HORSE_SDK_BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()

include(GNUInstallDirs)
set(_horse_install_targets horse_sdk horse_save)
if(HORSE_SDK_BUILD_DATA)
    list(APPEND _horse_install_targets horse_data)
endif()
install(TARGETS ${_horse_install_targets}
    EXPORT HorseSDKTargets
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
install(DIRECTORY include/horse
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)
install(
    DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../RE_Tools/src/horse_save/include/"
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    FILES_MATCHING PATTERN "*.h"
)
if(HORSE_SDK_BUILD_DATA)
    install(
        DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../RE_Tools/src/horse_data/include/"
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
        FILES_MATCHING PATTERN "*.h"
    )
endif()
install(EXPORT HorseSDKTargets
    FILE HorseSDKTargets.cmake
    NAMESPACE horse::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/HorseSDK
)

include(CMakePackageConfigHelpers)
write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/HorseSDKConfigVersion.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMinorVersion
)
configure_package_config_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/cmake/HorseSDKConfig.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/HorseSDKConfig.cmake"
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/HorseSDK
)
install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/HorseSDKConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/HorseSDKConfigVersion.cmake"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/HorseSDK
)
