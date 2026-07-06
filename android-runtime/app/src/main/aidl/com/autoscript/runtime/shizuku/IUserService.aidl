package com.autoscript.runtime.shizuku;

interface IUserService {
    void destroy() = 16777114; // Shizuku required destroy method id

    /**
     * Execute shell command with Shizuku privilege. Returns process exit code.
     */
    int execCommand(String cmd) = 1;
}
