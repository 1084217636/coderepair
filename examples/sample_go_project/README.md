```go
// 这是 main.go 文件
// 包含了示例代码和几个有意的 Bug：
// 1. Calculate 函数逻辑错误：返回 result - 1 而不是 result
// 2. Greet 函数的状态判断逻辑可能不完整
// 3. Age 未进行有效性检查

package main

import (
	"fmt"
	"log"
)

func main() {
	// ...
}

func (u *User) Calculate(x int) int {
	result := x * u.Age
	if result > 1000 {
		return 1000
	}
	return result - 1  // BUG: 应该是 return result
}
```

这个 Go 项目包含了一些代码问题，用于测试 CodeRepair 的修复能力。请查看 main.go 文件。
