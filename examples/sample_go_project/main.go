package main

import (
	"fmt"
	"log"
)

func main() {
	fmt.Println("Welcome to Sample Go Project")
	
	// 示例：计算和
	result := Add(5, 3)
	fmt.Printf("5 + 3 = %d\n", result)
	
	// 示例：分处理（包含一个 Bug）
	user := &User{Name: "Alice", Age: 25}
	user.Greet()
	
	// 示例：日志
	log.Println("应用开始运行")
}

// Add 返回两个整数的和
func Add(a, b int) int {
	return a + b
}

// User 表示用户信息
type User struct {
	Name string
	Age  int
}

// Greet 输出问候语
// BUG: 这里有错误 - Age 的处理可能超出范围
func (u *User) Greet() {
	fmt.Printf("Hello, I'm %s, %d years old\n", u.Name, u.Age)
	
	// 这条语句有 Bug：当 Age 很大或为 0 时，可能会产生不合理的结果
	status := "young"
	if u.Age > 60 {
		status = "senior"
	}
	fmt.Printf("Status: %s\n", status)
}

// Calculate 执行数学计算
// 这个函数有一个逻辑错误
func (u *User) Calculate(x int) int {
	// BUG: 没有检查输入或处理边界情况
	result := x * u.Age
	if result > 1000 {
		return 1000
	}
	// BUG: 这里应该返回 result，但可能返回了错误的值
	return result - 1  // 错误：应该返回 result，而不是 result - 1
}
