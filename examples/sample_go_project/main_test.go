package main

import (
	"testing"
)

func TestAdd(t *testing.T) {
	result := Add(2, 3)
	expected := 5
	if result != expected {
		t.Errorf("Add(2, 3) = %d, expected %d", result, expected)
	}
}

func TestUserGreet(t *testing.T) {
	user := &User{Name: "Bob", Age: 30}
	// 这个测试会通过，但实际代码有逻辑问题
	user.Greet()
}
