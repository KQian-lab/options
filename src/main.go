package main

import (
	"html/template"
	"log"
	"net/http"
)

func handler(w http.ResponseWriter, r *http.Request) {
	t, _ := template.ParseFiles("apps.html")
	t.Execute(w, nil)
}

func main() {
	http.HandleFunc("/", handler)
    log.Fatal(http.ListenAndServe("0.0.0.0:8080", nil))
}
