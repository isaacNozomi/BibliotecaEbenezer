package com.ebenezer.biblioteca

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            BibliotecaEbenezerApp()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BibliotecaEbenezerApp(viewModel: LibraryViewModel = viewModel()) {
    MaterialTheme {
        var showBooks by remember { mutableStateOf(true) }
        var selectedBookTitle by remember { mutableStateOf("") }
        val focusManager = LocalFocusManager.current

        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        if (showBooks) Text("Biblioteca Ebenezer")
                        else Text(selectedBookTitle.take(30))
                    },
                    navigationIcon = {
                        if (!showBooks) {
                            IconButton(onClick = { showBooks = true }) {
                                Icon(Icons.Default.ArrowBack, contentDescription = "Volver")
                            }
                        }
                    },
                    actions = {
                        if (showBooks) {
                            TextButton(onClick = { showBooks = false }) {
                                Text("Buscar")
                            }
                        }
                    }
                )
            }
        ) { padding ->
            if (showBooks) {
                val books by viewModel.books.collectAsState(initial = emptyList())
                LazyColumn(modifier = Modifier.padding(padding)) {
                    items(books) { book ->
                        ListItem(
                            headlineContent = { Text(book.titulo, fontWeight = FontWeight.Bold) },
                            supportingContent = { Text(book.codigo) },
                            modifier = Modifier.clickable {
                                viewModel.selectBook(book.id)
                                selectedBookTitle = book.titulo
                                showBooks = false
                            }
                        )
                    }
                }
            } else {
                val paragraphs by viewModel.paragraphs.collectAsState(initial = emptyList())
                val searchQuery = viewModel.searchQuery.collectAsState()
                val searchResults by viewModel.searchResults.collectAsState(initial = emptyList())

                Column(modifier = Modifier.padding(padding)) {
                    OutlinedTextField(
                        value = searchQuery.value,
                        onValueChange = { viewModel.updateSearchQuery(it) },
                        label = { Text("Buscar en este libro") },
                        modifier = Modifier.fillMaxWidth().padding(8.dp),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { focusManager.clearFocus() })
                    )

                    if (searchQuery.value.length >= 2) {
                        LazyColumn {
                            items(searchResults) { result ->
                                Card(modifier = Modifier.fillMaxWidth().padding(4.dp)) {
                                    Column(modifier = Modifier.padding(8.dp)) {
                                        Text(
                                            text = "${result.titulo} - Párrafo ${result.numero_parrafo}",
                                            fontWeight = FontWeight.Bold
                                        )
                                        Text(
                                            text = result.snippet.replace("<b>", "").replace("</b>", ""),
                                            fontSize = 14.sp
                                        )
                                    }
                                }
                            }
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(16.dp)
                        ) {
                            item {
                                Card(
                                    modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
                                ) {
                                    Text(
                                        text = selectedBookTitle,
                                        fontSize = 24.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(16.dp)
                                    )
                                }
                            }

                            itemsIndexed(paragraphs) { index, parrafo ->
                                // Determinar estilo según el campo tipo
                                val esTituloInterno = parrafo.tipo == 1
                                val esCita = parrafo.tipo == 2

                                Card(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                                ) {
                                    Column(modifier = Modifier.padding(12.dp)) {
                                        if (parrafo.numero_parrafo > 0) {
                                            Text(
                                                text = "${parrafo.numero_parrafo}",
                                                fontSize = 12.sp,
                                                color = MaterialTheme.colorScheme.primary,
                                                fontWeight = FontWeight.Bold
                                            )
                                            Spacer(modifier = Modifier.height(4.dp))
                                        }
                                        // Permitir seleccionar y copiar texto
                                        SelectionContainer {
                                            Text(
                                                text = parrafo.contenido,
                                                fontSize = when {
                                                    esTituloInterno -> 20.sp
                                                    esCita -> 16.sp
                                                    else -> 16.sp
                                                },
                                                fontWeight = if (esTituloInterno) FontWeight.Bold else FontWeight.Normal,
                                                fontStyle = if (esCita) FontStyle.Italic else FontStyle.Normal,
                                                lineHeight = 26.sp,
                                                color = when {
                                                    esTituloInterno -> MaterialTheme.colorScheme.primary
                                                    esCita -> MaterialTheme.colorScheme.secondary
                                                    else -> MaterialTheme.colorScheme.onSurface
                                                }
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}