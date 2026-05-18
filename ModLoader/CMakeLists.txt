cmake_minimum_required(VERSION 3.16)
project(HorseModLoader VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

if(NOT WIN32)
    message(FATAL_ERROR "HorseModLoader requires Windows (DLL injection)")
endif()

set(HORSE_SDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../SDK")

add_subdirectory("${HORSE_SDK_DIR}" "${CMAKE_BINARY_DIR}/horse_sdk_build")

add_library(HorseModLoader SHARED
    src/loader_dll.c
    src/loader_thread.c
    src/mod_host.c
    src/debug_console.c
    src/loader_config.c
    src/hook_manager.c
    src/overlay.c
)

target_include_directories(HorseModLoader PRIVATE
    "${HORSE_SDK_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
)

target_link_libraries(HorseModLoader PRIVATE horse_sdk)

add_executable(horse_inject src/injector.c)
target_link_libraries(horse_inject PRIVATE)

if(MSVC)
    target_compile_options(HorseModLoader PRIVATE /W4)
endif()

add_subdirectory(mods/example_mod)
