# Copyright 2022 Memrise

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import enum


class ExitCode(enum.IntEnum):
    SUCCESS = 0
    # 1 is returned when an uncaught exception is raised.
    UNCAUGHT_EXCEPTION = 1
    # Argparse returns 2 when bad args are passed.
    ARGUMENT_PARSING_ERROR = 2
    ERROR_DIFF = 3
    DEPRECATED = 4
